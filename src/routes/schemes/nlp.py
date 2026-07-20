from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional


class PushRequest(BaseModel):
    do_reset: Optional[bool] = False


class SearchRequest(BaseModel):
    text: str = Field(..., min_length=1)
    limit: Optional[int] = Field(default=5, ge=1, le=50)
    strategy: Optional[str] = Field(default=None, pattern="^(vector|bm25|hybrid)$")

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


class Citation(BaseModel):
    source_id: str = Field(..., description="Stable source reference shown in the answer UI, e.g. source_1")
    rank: int = Field(..., ge=1)
    score: float | None = None
    document_name: str | None = None
    page_number: int | None = None
    chunk_id: str | None = None


class SourceChunk(BaseModel):
    source_id: str
    rank: int = Field(..., ge=1)
    text: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalMetadata(BaseModel):
    strategy: str = "vector"
    requested_top_k: int = Field(..., ge=1)
    returned_count: int = Field(..., ge=0)
    vector_top_k: int | None = None
    bm25_top_k: int | None = None
    rerank_top_n: int | None = None
    min_relevance_score: float | None = None
    prompt_name: str | None = None
    prompt_version: str | None = None
    prompt_source: str | None = None


class ChatAnswerResponse(BaseModel):
    status: bool = True
    knowledge_base_id: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    source_chunks: list[SourceChunk] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    retrieval_metadata: RetrievalMetadata
    trace_id: str
    message: str
