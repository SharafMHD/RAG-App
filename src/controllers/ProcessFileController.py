from .BaseController import BaseController
from .ProjectController import ProjectController
import os
from models.enums.ProcessFileEnums import ProcessFileEnums
#from langchain.document_loaders import TextLoader, PyMuPDFLoader
from langchain_community.document_loaders import TextLoader,PyMuPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

class ProcessFileController(BaseController):

    def __init__(self , project_id: str):
        super().__init__()
        self.project_controller = ProjectController()
        self.project_id = project_id
        self.project_path = self.project_controller.get_project_path(project_id)
    
    def get_file_extension(self, file_id: str) -> str:
        return os.path.splitext(file_id)[1].lower()

    def get_file_loader(self, file_id: str):
        file_extension = self.get_file_extension(file_id)
        file_path = os.path.join(self.project_path, file_id)

        if file_extension == ProcessFileEnums.TXT.value:
            return TextLoader(file_path, encoding='utf-8')
        elif file_extension == ProcessFileEnums.PDF:
            return PyMuPDFLoader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
    
    def get_document_content(self, file_id: str):
        loader = self.get_file_loader( file_id)
        documents = loader.load()
        return documents

    def process_file(self, file_content: str, chunk_size: int=512000, overlap_size: int = 5120):
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap_size,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        file_content_text=[
            doc.page_content for doc in file_content
        ]
        file_content_metadata=[
            doc.metadata for doc in file_content    
        ]
        chuncks = text_splitter.create_documents(
            file_content_text,
            metadatas=file_content_metadata
        )
        return chuncks
