from functools import lru_cache
from typing import Any, Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "RAG APP"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"

    # Security settings
    API_KEY: str | None = None
    REQUIRE_API_KEY: bool = False
    CORS_ALLOWED_ORIGINS: list[str] = ["*"]
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    TRUSTED_HOSTS: list[str] = ["*"]

    # File processing settings
    FILE_ALLOWED_TYPES: list[str] = Field(
        default_factory=lambda: ["text/plain", "application/pdf"],
        validation_alias=AliasChoices("FILE_ALLOWED_TYPES", "FILE_ALLWOED_TYPES"),
    )
    FILE_ALLOWED_SIZE: int = Field(
        default=10,
        validation_alias=AliasChoices("FILE_ALLOWED_SIZE", "FILE_ALLOWED_SZIE"),
    )  # in MB
    UPLOAD_DIR: str = "assets/files"
    FILE_DEFAULT_CHUNK_SIZE: int = 900
    FILE_OVERLAP_SIZE: int = 150
    CHUNKING_STRATEGY: str = "page_recursive_v1"
    CHUNK_SIZE: int = 900
    CHUNK_OVERLAP: int = 150
    MIN_CHUNK_CHARS: int = 100
    PARENT_CHILD_CHUNKING_ENABLED: bool = False

    # PostgreSQL database config
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_MAIN_DB: str = "rag_app_db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "admin"

    # LLM settings
    GENERATION_BACKEND: Literal["OPENAI", "COHERE"] = "OPENAI"
    EMBEDDING_BACKEND: Literal["OPENAI", "COHERE"] = "OPENAI"
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None
    COHERE_API_KEY: str | None = None
    GENERATION_MODEL_ID: str | None = "gpt-4o-mini"
    EMBEDDING_MODEL_ID: str | None = "text-embedding-3-small"
    EMBEDDING_MODEL_SIZE: int | None = 1536
    DEFAULT_INPUT_MAX_TOKENS: int | None = 4096
    DEFAULT_OUTPUT_MAX_TOKENS: int | None = 1024
    DEFAULT_GENERATION_TEMPERATURE: float | None = 0.0

    # Vector DB settings
    VECTOR_DB_BACKEND: Literal["QDRANT", "PGVECTOR"] = "QDRANT"
    VECTOR_DB_PATH: str = "qdrant_data"
    VECTOR_DB_DISTANCE_METHOD: Literal["COSINE", "EUCLIDEAN", "DOT"] = "COSINE"
    VECTOR_DBS_DIR: str = "assets/vector_dbs"
    PGVECTOR_INDEX_THREADHOLD: int = 1000

    # Retrieval settings
    HYBRID_SEARCH_ENABLED: bool = True
    BM25_ENABLED: bool = False
    VECTOR_TOP_K: int = 30
    BM25_TOP_K: int = 30
    HYBRID_TOP_N: int = 10
    RRF_K: int = 60
    MIN_RELEVANCE_SCORE: float = 0.0
    QUERY_EXPANSION_ENABLED: bool = False
    QUERY_DECOMPOSITION_ENABLED: bool = False
    QUERY_PREPROCESSING_MAX_GENERATED_QUERIES: int = Field(default=3, ge=1, le=10)
    QUERY_PREPROCESSING_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0, le=30)
    QUERY_PREPROCESSING_MAX_OUTPUT_TOKENS: int = Field(default=128, ge=1, le=512)

    # Templates settings
    DEFAULT_LANGUAGE: str = "en"
    PRIMARY_LANGUAGE: str = "en"
    TEMPLATES_DIR: str = "templates"

    # Celery config
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_TASK_TIME_LIMIT: int = 600
    CELERY_TASK_ACKS_LATE: bool = True
    CELERY_WORKER_CONCURRENCY: int = 2
    CELERY_FLOWER_PASSWORD: str | None = None

    # Langfuse / prompting config
    LANGFUSE_ENABLED: bool = False
    langfuse_secret_key: str | None = Field(default=None, validation_alias=AliasChoices("LANGFUSE_SECRET_KEY", "langfuse_secret_key"))
    langfuse_public_key: str | None = Field(default=None, validation_alias=AliasChoices("LANGFUSE_PUBLIC_KEY", "langfuse_public_key"))
    langfuse_base_url: str | None = Field(default=None, validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL", "langfuse_base_url"))
    LANGFUSE_ENVIRONMENT: str | None = None
    LANGFUSE_RELEASE: str | None = None
    LANGFUSE_TRACE_SAMPLE_RATE: float | None = 1.0
    RAG_PROMPT_NAME: str = "rag-grounded-answer"
    RAG_PROMPT_LABEL: str | None = "production"
    REQUIRE_ANSWER_CITATIONS: bool = True
    STRICT_CITATION_VALIDATION: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        validate_default=True,
    )

    @field_validator(
        "GENERATION_BACKEND",
        "EMBEDDING_BACKEND",
        "VECTOR_DB_BACKEND",
        "VECTOR_DB_DISTANCE_METHOD",
        mode="before",
    )
    @classmethod
    def uppercase_enum_values(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().strip('"\'').upper()
        return value

    @field_validator("FILE_ALLOWED_TYPES", "CORS_ALLOWED_ORIGINS", "TRUSTED_HOSTS", mode="before")
    @classmethod
    def parse_list_values(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return value
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        if self.FILE_ALLOWED_SIZE <= 0:
            raise ValueError("FILE_ALLOWED_SIZE must be greater than 0 MB")
        if self.FILE_DEFAULT_CHUNK_SIZE <= 0:
            raise ValueError("FILE_DEFAULT_CHUNK_SIZE must be greater than 0")
        if self.FILE_OVERLAP_SIZE < 0:
            raise ValueError("FILE_OVERLAP_SIZE cannot be negative")
        if self.FILE_OVERLAP_SIZE >= self.FILE_DEFAULT_CHUNK_SIZE:
            raise ValueError("FILE_OVERLAP_SIZE must be smaller than FILE_DEFAULT_CHUNK_SIZE")
        if self.CHUNK_SIZE <= 0:
            raise ValueError("CHUNK_SIZE must be greater than 0")
        if self.CHUNK_OVERLAP < 0 or self.CHUNK_OVERLAP >= self.CHUNK_SIZE:
            raise ValueError("CHUNK_OVERLAP must be non-negative and smaller than CHUNK_SIZE")
        if self.MIN_CHUNK_CHARS < 0:
            raise ValueError("MIN_CHUNK_CHARS cannot be negative")
        if self.EMBEDDING_MODEL_SIZE is not None and self.EMBEDDING_MODEL_SIZE <= 0:
            raise ValueError("EMBEDDING_MODEL_SIZE must be greater than 0")
        if self.RATE_LIMIT_REQUESTS <= 0 or self.RATE_LIMIT_WINDOW_SECONDS <= 0:
            raise ValueError("rate limit settings must be greater than 0")
        if min(self.VECTOR_TOP_K, self.BM25_TOP_K, self.HYBRID_TOP_N, self.RRF_K) <= 0:
            raise ValueError("retrieval top-k settings must be greater than 0")
        if self.LANGFUSE_TRACE_SAMPLE_RATE is not None and not 0 <= self.LANGFUSE_TRACE_SAMPLE_RATE <= 1:
            raise ValueError("LANGFUSE_TRACE_SAMPLE_RATE must be between 0 and 1")
        if self.REQUIRE_API_KEY and not self.API_KEY:
            raise ValueError("API_KEY must be set when REQUIRE_API_KEY=true")
        if self.ENVIRONMENT == "production":
            if "*" in self.CORS_ALLOWED_ORIGINS:
                raise ValueError("CORS_ALLOWED_ORIGINS cannot contain '*' in production")
            if self.REQUIRE_API_KEY and not self.API_KEY:
                raise ValueError("API_KEY is required when API key auth is enabled in production")
        required_provider_keys = {
            "OPENAI": self.OPENAI_API_KEY,
            "COHERE": self.COHERE_API_KEY,
        }
        for provider in {self.GENERATION_BACKEND, self.EMBEDDING_BACKEND}:
            if self.ENVIRONMENT == "production" and not required_provider_keys.get(provider):
                raise ValueError(f"{provider}_API_KEY must be set in production")
        return self

    @property
    def FILE_ALLWOED_TYPES(self) -> list[str]:
        """Backward-compatible alias for the previous misspelled setting."""
        return self.FILE_ALLOWED_TYPES

    @property
    def FILE_ALLOWED_SZIE(self) -> int:
        """Backward-compatible alias for the previous misspelled setting."""
        return self.FILE_ALLOWED_SIZE


@lru_cache
def get_settings() -> Settings:
    """Return validated application settings loaded from env vars or `.env`."""
    return Settings()
