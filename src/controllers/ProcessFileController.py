from .BaseController import BaseController
from .KnowledgeBaseController import KnowledgeBaseController
import os
from sqlalchemy.dialects.postgresql import UUID
from models.enums.ProcessFileEnums import ProcessFileEnums
from langchain_community.document_loaders import TextLoader
from typing import List
from dataclasses import dataclass
from helpers.config import get_settings
from services.document_processing import ChunkingConfig, PDFExtractor, PageAwareRecursiveChunker

@dataclass
class ProcessedDocument:
    page_content: str
    metadata: dict

class ProcessFileController(BaseController):

    def __init__(self , knowledge_base_id: UUID):
        super().__init__()
        self.knowledge_base_controller = KnowledgeBaseController()
        self.knowledge_base_id = knowledge_base_id
        self.knowledge_base_path = self.knowledge_base_controller.get_knowledge_base_path(knowledge_base_id)
    
    def get_file_extension(self, file_id: str) -> str:
        return os.path.splitext(file_id)[1].lower()

    def get_file_loader(self, file_id: str):
        file_extension = self.get_file_extension(file_id)
        file_path = os.path.join(self.knowledge_base_path, file_id)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        if not file_extension:
            with open(file_path, "rb") as file:
                if file.read(5).startswith(b"%PDF"):
                    file_extension = ProcessFileEnums.PDF.value
        
        if file_extension == ProcessFileEnums.TXT.value:
            return TextLoader(file_path, encoding='utf-8')
        elif file_extension == ProcessFileEnums.PDF.value:
            return PDFExtractor()
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
    
    def get_document_content(self, file_id: str):
        loader = self.get_file_loader(file_id)
        file_path = os.path.join(self.knowledge_base_path, file_id)
        if isinstance(loader, PDFExtractor):
            return loader.extract(file_path=file_path, document_name=file_id)
        if loader:
            documents = loader.load()
            for index, document in enumerate(documents, start=1):
                metadata = dict(getattr(document, "metadata", {}) or {})
                metadata.update({
                    "source": file_id,
                    "document_name": file_id,
                    "file_name": file_id,
                    "page": metadata.get("page") or index,
                    "page_number": metadata.get("page_number") or metadata.get("page") or index,
                    "extractor": "text_loader_v1",
                })
                document.metadata = metadata
            return documents
        return None

    def process_file(self, file_content: str, chunk_size: int=900, overlap_size: int = 150):
        settings = get_settings()
        chunker = PageAwareRecursiveChunker(
            ChunkingConfig(
                chunk_size=chunk_size or settings.CHUNK_SIZE,
                chunk_overlap=overlap_size if overlap_size is not None else settings.CHUNK_OVERLAP,
                min_chunk_chars=settings.MIN_CHUNK_CHARS,
                chunking_strategy=settings.CHUNKING_STRATEGY,
                embedding_model=settings.EMBEDDING_MODEL_ID,
                parent_child_enabled=settings.PARENT_CHILD_CHUNKING_ENABLED,
            )
        )
        chunks = chunker.split(file_content)
        return [ProcessedDocument(page_content=chunk.page_content, metadata=chunk.metadata) for chunk in chunks]
    
    def process_doc_simple_splitter(self, text: List[str], chunk_size: int, metadata: List[dict], spliiter_tag: str = "\n", overlap_size: int = 0) -> List[ProcessedDocument]:
        full_text = spliiter_tag.join(doc.strip() for doc in text if doc and doc.strip())
        if not full_text:
            return []

        chunk_size = max(1, int(chunk_size))
        overlap_size = max(0, min(int(overlap_size or 0), chunk_size - 1))
        chunks = []
        start = 0

        while start < len(full_text):
            end = min(start + chunk_size, len(full_text))
            chunk_text = full_text[start:end].strip()
            if chunk_text:
                chunks.append(
                    ProcessedDocument(
                        page_content=chunk_text,
                        metadata={"source_documents": metadata}
                    )
                )
            if end >= len(full_text):
                break
            start = end - overlap_size

        return chunks
                
