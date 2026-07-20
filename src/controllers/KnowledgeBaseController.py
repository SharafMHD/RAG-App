from .BaseController import BaseController
from fastapi import UploadFile
from models import ResponseStatus
import os
from uuid import UUID

class KnowledgeBaseController(BaseController):
    def __init__(self):
        super().__init__()

    def get_knowledge_base_path(self, knowledge_base_id: UUID) :
        knowledge_base_dir = os.path.join(self.file_dir, str(knowledge_base_id))
        if not os.path.exists(knowledge_base_dir):
            os.makedirs(knowledge_base_dir)
        return knowledge_base_dir