from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Iterable

from .text_cleaner import clean_extracted_text


@dataclass
class ChunkingConfig:
    chunk_size: int = 900
    chunk_overlap: int = 150
    min_chunk_chars: int = 100
    chunking_strategy: str = "page_recursive_v1"
    embedding_model: str | None = None
    parent_child_enabled: bool = False


@dataclass
class ProcessedDocumentChunk:
    page_content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class PageAwareRecursiveChunker:
    """Split documents page-by-page while preserving citation metadata."""

    def __init__(self, config: ChunkingConfig):
        if config.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")
        if config.chunk_overlap < 0 or config.chunk_overlap >= config.chunk_size:
            raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size")
        if config.min_chunk_chars < 0:
            raise ValueError("min_chunk_chars cannot be negative")
        self.config = config

    def split(self, pages: Iterable[Any], document_name: str | None = None) -> list[ProcessedDocumentChunk]:
        chunks: list[ProcessedDocumentChunk] = []
        global_index = 0

        for page_index, page in enumerate(pages, start=1):
            text = clean_extracted_text(getattr(page, "page_content", "") or "")
            if not text:
                continue

            base_metadata = dict(getattr(page, "metadata", {}) or {})
            page_number = base_metadata.get("page_number") or base_metadata.get("page") or page_index
            source = document_name or base_metadata.get("document_name") or base_metadata.get("file_name") or base_metadata.get("source")
            page_parts = self._split_text(text)

            for page_chunk_index, chunk_text in enumerate(page_parts, start=1):
                if len(chunk_text) < self.config.min_chunk_chars and len(page_parts) > 1:
                    continue
                global_index += 1
                metadata = {
                    **base_metadata,
                    "source": source,
                    "document_name": source,
                    "file_name": source,
                    "page": page_number,
                    "page_number": page_number,
                    "chunk_index": global_index,
                    "page_chunk_index": page_chunk_index,
                    "chunking_strategy": self.config.chunking_strategy,
                    "embedding_model": self.config.embedding_model,
                    "content_hash": sha256(chunk_text.encode("utf-8")).hexdigest(),
                    "parent_chunk_id": None,
                    "parent_child_chunking_enabled": self.config.parent_child_enabled,
                }
                chunks.append(ProcessedDocumentChunk(page_content=chunk_text, metadata=metadata))

        return chunks

    def _split_text(self, text: str) -> list[str]:
        if len(text) <= self.config.chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text):
            hard_end = min(start + self.config.chunk_size, len(text))
            end = self._best_boundary(text, start, hard_end)
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(chunk_text)
            if hard_end >= len(text):
                break
            start = max(end - self.config.chunk_overlap, start + 1)
        return chunks

    def _best_boundary(self, text: str, start: int, hard_end: int) -> int:
        if hard_end >= len(text):
            return len(text)

        window = text[start:hard_end]
        min_end = max(int(len(window) * 0.6), 1)
        for separator in ("\n\n", "\n", ". ", "؟ ", "! ", " "):
            pos = window.rfind(separator)
            if pos >= min_end:
                return start + pos + len(separator)
        return hard_end
