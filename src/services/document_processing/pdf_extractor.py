from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import PyMuPDFLoader

from .text_cleaner import clean_extracted_text


@dataclass
class ExtractedPage:
    page_content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class PDFExtractor:
    """Page-aware PDF extraction boundary.

    The rest of the ingestion pipeline should depend on this small shape, not on
    a specific PDF library. PyMuPDFLoader uses zero-based page indexes, so this
    service normalizes page metadata to one-based page numbers for citations.
    """

    def extract(self, file_path: str | Path, document_name: str | None = None) -> list[ExtractedPage]:
        path = Path(file_path)
        document_name = document_name or path.name
        documents = PyMuPDFLoader(str(path)).load()
        pages: list[ExtractedPage] = []

        for index, document in enumerate(documents, start=1):
            metadata = dict(getattr(document, "metadata", {}) or {})
            raw_page = metadata.get("page")
            try:
                page_number = int(raw_page) + 1 if raw_page is not None else index
            except (TypeError, ValueError):
                page_number = index

            metadata.update(
                {
                    "source": document_name,
                    "document_name": document_name,
                    "file_name": document_name,
                    "page": page_number,
                    "page_number": page_number,
                    "extractor": "pymupdf_v1",
                }
            )
            pages.append(
                ExtractedPage(
                    page_content=clean_extracted_text(getattr(document, "page_content", "")),
                    metadata=metadata,
                )
            )

        return pages
