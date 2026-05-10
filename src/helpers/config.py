from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Provide reasonable defaults for development to avoid startup failures
    APP_NAME: str = "RAG APP"
    APP_VERSION: str = "0.1.0"
    OPENAI_API_KEY: str = ""
    ENVIRONMENT: str = "development"

    FILE_ALLWOED_TYPES: list[str] = ["text/plain", "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
    FILE_ALLOWED_SZIE: int = 10 # in MB
    UPLOAD_DIR: str = "assets/files"
    FILE_DEFAULT_CHUNK_SIZE: int = 512000 # in kb
    FILE_OVERLAP_SIZE: int = 5120 # in kbs

    # MONGODB_URL:str = "mongodb://localhost:27017"
    # MONGODB_DB_NAME: str = "rag_app_db"
    
    # PostgreSQL Database config
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_MAIN_DB: str = "rag_app_db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "admin"  

    GENERATION_BACKEND: str
    EMBEDDING_BACKEND: str

    OPENAI_API_KEY: str = None
    OPENAI_BASE_URL: str = None
    COHERE_API_KEY: str =None

    # GENERATION_MODEL_ID_LITRAL: List[str] = None
    GENERATION_MODEL_ID: str =None
    EMBEDDING_MODEL_ID: str =None
    EMBEDDING_MODEL_SIZE:int = None

    DEFAULT_INPUT_MAX_TOKENS :int = None
    DEFAULT_OUTPUT_MAX_TOKENS :int = None
    DEFAULT_GENERATION_TEMPERATURE:float = None

#================== Vector DB Settings ===============================
    # VECTOR_DB_BACKEND_LITERAL: List[str] = None
    VECTOR_DB_BACKEND: str
    VECTOR_DB_PATH:str= "qdrant_data"
    VECTOR_DB_DISTANCE_METHOD:str=None
    VECTOR_DBS_DIR: str = "assets/vector_dbs/"
    PGVECTOR_INDEX_THREADHOLD: int = 1000
#================== Templates Settings ===============================
    DEFAULT_LANGUAGE: str = "en"    
    PRIMARY_LANGUAGE: str = "en"    
    TEMPLATES_DIR: str = "templates"
    # pydantic v2 style configuration for loading an env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

def get_settings() -> Settings:
    """Return a Settings instance.

    This will load values from environment variables or from `.env` if present.
    Defaults are provided to keep the app usable in development when env vars
    aren't set.
    """
    return Settings()