from .BaseController import BaseController
from .ProjectController import ProjectController
import os
from sqlalchemy.dialects.postgresql import UUID
from models.enums.ProcessFileEnums import ProcessFileEnums
from langchain_community.document_loaders import TextLoader,PyMuPDFLoader
# from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List
from dataclasses import dataclass

@dataclass
class ProcessedDocument:
    page_content: str
    metadata: dict

class ProcessFileController(BaseController):

    def __init__(self , project_id: UUID):
        super().__init__()
        self.project_controller = ProjectController()
        self.project_id = project_id
        self.project_path = self.project_controller.get_project_path(project_id)
    
    def get_file_extension(self, file_id: str) -> str:
        return os.path.splitext(file_id)[1].lower()

    def get_file_loader(self, file_id: str):
        file_extension = self.get_file_extension(file_id)
        file_path = os.path.join(self.project_path, file_id)
        if not os.path.exists(file_path):
            raise None
        
        if file_extension == ProcessFileEnums.TXT.value:
            return TextLoader(file_path, encoding='utf-8')
        elif file_extension == ProcessFileEnums.PDF:
            return PyMuPDFLoader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
    
    def get_document_content(self, file_id: str):
        loader = self.get_file_loader( file_id)
        if loader:
            documents = loader.load()
            return documents
        return None

    def process_file(self, file_content: str, chunk_size: int=512000, overlap_size: int = 5120):
        # text_splitter = RecursiveCharacterTextSplitter(
        #     chunk_size=chunk_size,
        #     chunk_overlap=overlap_size,
        #     length_function=len,
        #     separators=["\n\n", "\n", " ", ""]
        # )
        file_content_text=[
            doc.page_content for doc in file_content
        ]
        file_content_metadata=[
            doc.metadata for doc in file_content    
        ]
        # chuncks = text_splitter.create_documents(
        #     file_content_text,
        #     metadatas=file_content_metadata
        # )
        chunks= self.process_doc_simple_splitter(file_content_text, chunk_size, file_content_metadata)
        return chunks
    
    def process_doc_simple_splitter( self,text: List[str],chunk_size: int,metadata: List[dict],spliiter_tag: str = "\n") -> List[ProcessedDocument]:
        full_text = " ".join(text)

        # Split the full text into chunks
        lines = [
            doc.strip()
            for doc in full_text.split(spliiter_tag)
            if len(doc.strip()) > 1
        ]

        chunks = []
        current_chunk = ""

        for line in lines:
            current_chunk += line + spliiter_tag

            if len(current_chunk) >= chunk_size:
                chunks.append(
                    ProcessedDocument(
                        page_content=current_chunk.strip(),
                        metadata=metadata
                    )
                )

                current_chunk = ""

        # Add remaining chunk
        if current_chunk:
            chunks.append(
                ProcessedDocument(
                    page_content=current_chunk.strip(),
                    metadata=metadata
                )
            )

        return chunks
                
