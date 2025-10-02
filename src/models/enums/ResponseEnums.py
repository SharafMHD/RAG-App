from enum import Enum

class ResponseStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    FILE_UPLOAD_ERROR = "file upload failed"
    FILE_UPLODED_SUCCESS = "file uploaded successfully"
    FILE_SZIE_EXCEEDS = "file size exceeds the allowed limit"
    FILE_TYPE_NOT_ALLOWED = "file type is not allowed"
    