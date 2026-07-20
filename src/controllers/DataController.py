from .BaseController import BaseController
from fastapi import UploadFile
from models import ResponseStatus
from .KnowledgeBaseController import KnowledgeBaseController
import uuid
import os
import re
class DataController(BaseController):
    def __init__(self):
        super().__init__()

    def validate_uploded_file(self, file: UploadFile) -> bool:
        if file.content_type not in self.app_settings.FILE_ALLOWED_TYPES:
            return False, ResponseStatus.FILE_TYPE_NOT_ALLOWED.value
        if file.size is not None and file.size > self.app_settings.FILE_ALLOWED_SIZE * 1024 * 1024:
            return False , ResponseStatus.FILE_SZIE_EXCEEDS.value
        return True , "file is valid"
    
    def generate_unique_filepath(self, original_filename: str, knowledge_base_id:uuid) -> str:
        extension = os.path.splitext(original_filename)[1]
        unique_name = f"{uuid.uuid4()}"
        # Use an instance of KnowledgeBaseController (get_knowledge_base_path is an instance method)
        knowledge_base_controller = KnowledgeBaseController()
        knowledge_base_path = knowledge_base_controller.get_knowledge_base_path(knowledge_base_id)
        clean_name = self.get_clean_filename(original_filename)
        unique_file_name = os.path.join(knowledge_base_path, unique_name + "_" + clean_name)
        while os.path.exists(unique_file_name):
            unique_name = f"{uuid.uuid4()}"
            unique_file_name = os.path.join(knowledge_base_path, unique_name + "_" + clean_name)
        return unique_file_name,unique_name + "_" + clean_name
    # clean the filename to prevent directory traversal attacks using regix
    def get_clean_filename(self, filename: str) -> str:

        filename = os.path.basename(filename or "uploaded_file")
        # remove any special characters except for alphanumerics, dots, dashes, and underscores
        cleaned_filename = re.sub(r'[^a-zA-Z0-9.\-_]', '_', filename)
        cleaned_filename = cleaned_filename.strip("._") or "uploaded_file"
        return cleaned_filename[:180]