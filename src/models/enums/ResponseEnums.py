from enum import Enum

class ResponseStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    FILE_UPLOAD_ERROR = "file_upload_error"
    FILE_UPLODED_SUCCESS = "file_upload_success"
    FILE_SZIE_EXCEEDS = "file_size_exceeds"
    FILE_TYPE_NOT_ALLOWED = "file_type_not_allowed"
    