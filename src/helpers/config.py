from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # pydantic v2 style configuration for loading an env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    """Return a Settings instance.

    This will load values from environment variables or from `.env` if present.
    Defaults are provided to keep the app usable in development when env vars
    aren't set.
    """
    return Settings()