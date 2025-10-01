from .BaseController import BaseController
from fastapi import UploadFile
from models import ResponseStatus

class DataController(BaseController):
    def __init__(self):
        super().__init__()

    def validate_uploded_file(self, file: UploadFile) -> bool:
        print(self.app_settings.FILE_ALLWOED_TYPES)
        if file.content_type not in self.app_settings.FILE_ALLWOED_TYPES :
            return False, ResponseStatus.FILE_TYPE_NOT_ALLOWED.value
        if file.size > self.app_settings.FILE_ALLOWED_SZIE * 1024 * 1024:
            return False , ResponseStatus.FILE_SZIE_EXCEEDS.value
        return True , "file is valid"
    