from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class PushRequest(BaseModel):
    do_reset: bool | None = False


class QueryPreprocessingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expand: bool = Field(default=False, strict=True)
    decompose: bool = Field(default=False, strict=True)
    max_generated_queries: int | None = Field(default=None, ge=1, le=10, strict=True)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1)
    limit: int | None = Field(default=5, ge=1, le=50, strict=True)
    strategy: str | None = Field(default=None, pattern="^(vector|bm25|hybrid)$")
    preprocessing: QueryPreprocessingRequest | None = None

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., description="Stable source reference shown in the answer UI, e.g. source_1")
    rank: int = Field(..., ge=1)
    score: float | None = None
    document_name: str | None = None
    page_number: int | None = None
    chunk_id: str | None = None


class SourceChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    rank: int = Field(..., ge=1)
    text: str
    score: float | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class QueryPreprocessingMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["disabled", "applied", "fallback"]
    original_query: str
    generated_queries: list[str] = Field(default_factory=list)
    generated_query_count: int = Field(ge=0)


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
    preprocessing: QueryPreprocessingMetadata | None = None


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


class _StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _FeedbackContractModel(_StrictContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class AnswerStreamTokenPayload(_StrictContractModel):
    content: str = Field(..., min_length=1)


class AnswerStreamFinalPayload(_StrictContractModel):
    response: ChatAnswerResponse


class AnswerStreamErrorPayload(_StrictContractModel):
    detail: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class AnswerStreamDonePayload(_StrictContractModel):
    pass


class AnswerStreamTokenEvent(_StrictContractModel):
    event: Literal["token"]
    data: AnswerStreamTokenPayload


class AnswerStreamFinalEvent(_StrictContractModel):
    event: Literal["final"]
    data: AnswerStreamFinalPayload


class AnswerStreamErrorEvent(_StrictContractModel):
    event: Literal["error"]
    data: AnswerStreamErrorPayload


class AnswerStreamDoneEvent(_StrictContractModel):
    event: Literal["done"]
    data: AnswerStreamDonePayload


type AnswerStreamEvent = Annotated[
    AnswerStreamTokenEvent | AnswerStreamFinalEvent | AnswerStreamErrorEvent | AnswerStreamDoneEvent,
    Field(discriminator="event"),
]
# Frontend answer delivery uses SSE; NDJSON remains reserved for backend data and chunk pipelines.

type FeedbackRating = Literal["thumbs_up", "thumbs_down"]
type FeedbackDeliveryStatus = Literal["disabled", "sent", "failed"]


class FeedbackRequest(_FeedbackContractModel):
    trace_id: str = Field(..., min_length=1)
    knowledge_base_id: str = Field(..., min_length=1)
    rating: FeedbackRating
    comment: str | None = Field(default=None, max_length=2000)
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    citations: list[Citation]
    source_chunks: list[SourceChunk]


class FeedbackResponse(_FeedbackContractModel):
    status: bool = True
    trace_id: str = Field(..., min_length=1)
    rating: FeedbackRating
    comment: str | None = Field(default=None, max_length=2000)
    langfuse_status: FeedbackDeliveryStatus = "disabled"
    message: str = Field(..., min_length=1)
