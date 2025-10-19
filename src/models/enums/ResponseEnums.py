from enum import Enum

class ResponseStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    FILE_UPLOAD_ERROR = "file upload failed"
    FILE_UPLODED_SUCCESS = "file uploaded successfully"
    FILE_SZIE_EXCEEDS = "file size exceeds the allowed limit"
    FILE_TYPE_NOT_ALLOWED = "file type is not allowed"
    FILE_PROCESSING_ERROR = "file processing failed"
    FILE_PROCESSED_SUCCESS = "file processed successfully"
    FILE_NOT_FOUND_IN_PROJECT = "file not found in the specified project"
    PROJECT_NOT_FOUND_ERROR = "project not found"
    NLP_INDEXING_SUCCESS = "NLP indexing completed successfully"
    NLP_INDEXING_ERROR = "NLP indexing failed"
    