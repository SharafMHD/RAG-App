from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic import JsonValue

from models import ResponseStatus
from models.db_schemes import RetrievedDocuments
from routes.schemes.nlp import (
    ChatAnswerResponse,
    Citation,
    QueryPreprocessingMetadata,
    RetrievalMetadata,
    SourceChunk,
)
from services.answer_validation import validate_generated_answer
from services.prompt_service import PromptBundle
from services.query_preprocessing import (
    QueryPreprocessingMetadata as ServiceQueryPreprocessingMetadata,
)

type ChatHistory = list[dict[str, str]]


class AnswerTrace(Protocol):
    def update(
        self,
        *,
        input: dict[str, JsonValue],
        output: dict[str, JsonValue],
        metadata: dict[str, JsonValue],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class AnswerFinalizationRequest:
    knowledge_base_id: UUID
    query_text: str
    raw_answer: str | None
    full_prompt: str | None
    chat_history: ChatHistory | None
    retrieved_documents: list[RetrievedDocuments]
    limit: int
    trace_id: str
    prompt_bundle: PromptBundle | None
    preprocessing: ServiceQueryPreprocessingMetadata
    require_citations: bool
    strict_citation_validation: bool
    trace: AnswerTrace | None


def should_report_generation_failure(answer: str | None, retrieved_documents: list[RetrievedDocuments]) -> bool:
    return bool(retrieved_documents) and (answer is None or not answer.strip())


def preprocessing_metadata(metadata: ServiceQueryPreprocessingMetadata) -> QueryPreprocessingMetadata:
    return QueryPreprocessingMetadata(
        status=metadata.status,
        original_query=metadata.original_query,
        generated_queries=list(metadata.generated_queries),
        generated_query_count=metadata.generated_query_count,
    )


def build_chat_contract(
    knowledge_base_id: UUID,
    answer: str,
    retrieved_documents: list[RetrievedDocuments],
    limit: int,
    trace_id: str,
    prompt_bundle: PromptBundle | None = None,
    cited_source_ids: list[str] | None = None,
    preprocessing_metadata: QueryPreprocessingMetadata | None = None,
) -> ChatAnswerResponse:
    citations = []
    source_chunks = []
    scores = []
    include_all_citations = cited_source_ids is None
    cited_source_ids = cited_source_ids or []

    for rank, document in enumerate(retrieved_documents, start=1):
        metadata = getattr(document, "metadata", None) or {}
        score = getattr(document, "score", None)
        if score is not None:
            scores.append(float(score))
        source_id = f"source_{rank}"
        chunk_id = getattr(document, "chunk_id", None) or _metadata_value(metadata, "chunk_id", "id")
        if include_all_citations or source_id in cited_source_ids:
            citations.append(Citation(
                source_id=source_id,
                rank=rank,
                score=score,
                document_name=_metadata_value(metadata, "document_name", "file_name", "source"),
                page_number=getattr(document, "page_number", None) or _metadata_value(metadata, "page_number", "page"),
                chunk_id=str(chunk_id) if chunk_id is not None else None,
            ))
        source_chunks.append(SourceChunk(
            source_id=source_id,
            rank=rank,
            text=getattr(document, "text", ""),
            score=score,
            metadata=metadata,
        ))

    confidence = max(scores) if scores else None
    if confidence is not None:
        confidence = max(0.0, min(1.0, confidence))

    return ChatAnswerResponse(
        knowledge_base_id=str(knowledge_base_id),
        answer=answer,
        citations=citations,
        source_chunks=source_chunks,
        confidence=confidence,
        retrieval_metadata=RetrievalMetadata(
            strategy=(getattr(retrieved_documents[0], "retrieval_mode", None) if retrieved_documents else None) or "vector",
            requested_top_k=limit,
            returned_count=len(retrieved_documents),
            vector_top_k=limit,
            prompt_name=getattr(prompt_bundle, "prompt_name", None),
            prompt_version=getattr(prompt_bundle, "prompt_version", None),
            prompt_source=getattr(prompt_bundle, "prompt_source", None),
            preprocessing=preprocessing_metadata,
        ),
        trace_id=trace_id,
        message=ResponseStatus.NLP_RAG_ANSWER_SUCCESS.value,
    )


def finalize_answer(request: AnswerFinalizationRequest) -> ChatAnswerResponse | None:
    if should_report_generation_failure(request.raw_answer, request.retrieved_documents):
        return None

    available_source_ids = [f"source_{index + 1}" for index, _ in enumerate(request.retrieved_documents)]
    validated_answer = validate_generated_answer(
        request.raw_answer or "",
        available_source_ids=available_source_ids,
        query_text=request.query_text,
        require_citations=request.require_citations,
        strict_citation_validation=request.strict_citation_validation,
    )
    _update_answer_trace(request, validated_answer.model_dump())

    response = build_chat_contract(
        knowledge_base_id=request.knowledge_base_id,
        answer=validated_answer.answer,
        retrieved_documents=request.retrieved_documents,
        limit=request.limit,
        trace_id=request.trace_id,
        prompt_bundle=request.prompt_bundle,
        cited_source_ids=validated_answer.cited_source_ids,
        preprocessing_metadata=preprocessing_metadata(request.preprocessing),
    )
    if validated_answer.confidence is not None:
        response.confidence = validated_answer.confidence
    return response


def _metadata_value(metadata: dict, *keys: str):
    for key in keys:
        if key in metadata and metadata[key] is not None:
            return metadata[key]
    return None


def _update_answer_trace(request: AnswerFinalizationRequest, output: dict[str, JsonValue]) -> None:
    if request.trace is None:
        return

    try:
        request.trace.update(
            input={
                "query": request.query_text,
                "prompt": request.full_prompt,
                "chat_history": request.chat_history,
            },
            output=output,
            metadata={
                "knowledge_base_id": str(request.knowledge_base_id),
                "retrieved_count": len(request.retrieved_documents),
                "prompt_name": getattr(request.prompt_bundle, "prompt_name", None),
                "prompt_version": getattr(request.prompt_bundle, "prompt_version", None),
                "prompt_source": getattr(request.prompt_bundle, "prompt_source", None),
                "preprocessing_status": request.preprocessing.status,
            },
        )
    except (AttributeError, OSError, RuntimeError, ValueError):
        return
