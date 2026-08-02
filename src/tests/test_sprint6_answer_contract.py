from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID, uuid4

import anyio

from helpers.config import Settings
from models.db_schemes import RetrievedDocuments
from routes import nlp as nlp_routes
from routes.schemes.nlp import SearchRequest
from services.answer_finalization import (
    AnswerFinalizationRequest,
    build_chat_contract,
    finalize_answer,
    preprocessing_metadata,
)
from services.answer_validation import no_answer_text
from services.prompt_service import PromptBundle
from services.query_preprocessing import QueryPreprocessingMetadata


class RecordingTrace:
    def __init__(self) -> None:
        self.output = None

    def update(self, *, input, output, metadata) -> None:
        self.output = output


class FailingTrace:
    def update(self, *, input, output, metadata) -> None:
        raise RuntimeError("trace update failed")


class RecordingLangfuseService:
    def __init__(self, trace: RecordingTrace) -> None:
        self.trace = trace

    def create_trace_id(self) -> str:
        return "trace-1"

    @contextmanager
    def trace_answer(self, trace_id, *, input, metadata):
        yield self.trace


class AnswerController:
    def __init__(self, **kwargs) -> None:
        pass

    async def answer_rag_query_with_metadata(self, **kwargs):
        return (
            "Grounded result [source_1]",
            "full prompt",
            [{"role": "system", "content": "system prompt"}],
            [_document()],
            _prompt_bundle(),
            _preprocessing(),
        )


class KnowledgeBaseModel:
    async def get_knowledge_base_or_create(self, knowledge_base_id: UUID):
        return SimpleNamespace(knowledge_base_id=knowledge_base_id)


def _document() -> RetrievedDocuments:
    return RetrievedDocuments(
        text="Grounded source text",
        score=0.8,
        chunk_id="chunk-1",
        page_number=4,
        metadata={"document_name": "policy.pdf"},
        retrieval_mode="hybrid",
    )


def _prompt_bundle() -> PromptBundle:
    return PromptBundle(
        system_prompt="system prompt",
        footer_prompt="footer prompt",
        prompt_name="rag-grounded-answer",
        prompt_version="1",
        prompt_source="local",
    )


def _preprocessing() -> QueryPreprocessingMetadata:
    return QueryPreprocessingMetadata(
        status="disabled",
        original_query="What is covered?",
        generated_queries=(),
    )


def _finalization_request(
    *,
    raw_answer: str | None,
    retrieved_documents: list[RetrievedDocuments],
    trace: RecordingTrace | FailingTrace | None = None,
) -> AnswerFinalizationRequest:
    return AnswerFinalizationRequest(
        knowledge_base_id=uuid4(),
        query_text="What is covered?",
        raw_answer=raw_answer,
        full_prompt="full prompt",
        chat_history=[{"role": "system", "content": "system prompt"}],
        retrieved_documents=retrieved_documents,
        limit=5,
        trace_id="trace-1",
        prompt_bundle=_prompt_bundle(),
        preprocessing=_preprocessing(),
        require_citations=True,
        strict_citation_validation=True,
        trace=trace,
    )


def test_non_streaming_answer_endpoint_keeps_the_legacy_response_shape(monkeypatch):
    # Given
    trace = RecordingTrace()
    langfuse_service = RecordingLangfuseService(trace)

    async def create_instance(**kwargs):
        return KnowledgeBaseModel()

    monkeypatch.setattr(
        nlp_routes.KnowledgeBaseDataModel, "create_instance", create_instance
    )
    monkeypatch.setattr(nlp_routes, "NLPController", AnswerController)
    request = SimpleNamespace(
        app=SimpleNamespace(
            db_client=None,
            langfuse_service=langfuse_service,
            prompt_service=SimpleNamespace(),
            generation_client=SimpleNamespace(),
            embedding_client=SimpleNamespace(),
            vector_db_client=SimpleNamespace(),
            template_parser=SimpleNamespace(),
        )
    )

    # When
    response = anyio.run(
        nlp_routes.answer_rag,
        request,
        uuid4(),
        SearchRequest(text="What is covered?", limit=5, strategy="hybrid"),
        Settings(_env_file=None, LANGFUSE_ENABLED=False),
    )

    # Then
    payload = response.model_dump()
    assert set(payload) == {
        "status",
        "knowledge_base_id",
        "answer",
        "citations",
        "source_chunks",
        "confidence",
        "retrieval_metadata",
        "trace_id",
        "message",
    }
    assert payload["answer"] == "Grounded result [source_1]"
    assert payload["citations"][0]["source_id"] == "source_1"
    assert payload["source_chunks"][0]["text"] == "Grounded source text"
    assert trace.output is not None


def test_shared_finalizer_uses_the_validated_answer_for_response_and_trace():
    # Given
    trace = RecordingTrace()
    request = _finalization_request(
        raw_answer="The policy applies to the covered party.",
        retrieved_documents=[_document()],
        trace=trace,
    )

    # When
    response = finalize_answer(request)

    # Then
    assert response is not None
    assert response.answer == "The policy applies to the covered party. [source_1]"
    assert response.citations[0].source_id == "source_1"
    assert trace.output == {
        "answer": "The policy applies to the covered party. [source_1]",
        "cited_source_ids": ["source_1"],
        "is_answered": True,
        "confidence": None,
    }


def test_shared_finalizer_uses_no_answer_contract_for_invalid_citation_and_no_context():
    # Given
    invalid_citation_request = _finalization_request(
        raw_answer="Incorrect citation [source_9].",
        retrieved_documents=[_document()],
    )
    no_context_request = _finalization_request(raw_answer=None, retrieved_documents=[])

    # When
    invalid_citation_response = finalize_answer(invalid_citation_request)
    no_context_response = finalize_answer(no_context_request)

    # Then
    assert invalid_citation_response is not None
    assert invalid_citation_response.answer == no_answer_text("What is covered?")
    assert invalid_citation_response.citations == []
    assert len(invalid_citation_response.source_chunks) == 1
    assert no_context_response is not None
    assert no_context_response.answer == no_answer_text("What is covered?")
    assert no_context_response.citations == []
    assert no_context_response.source_chunks == []


def test_shared_finalizer_and_contract_builder_keep_citations_and_source_chunks_single_sourced():
    # Given
    request = _finalization_request(
        raw_answer="Grounded result [source_1]",
        retrieved_documents=[_document()],
    )

    # When
    response = finalize_answer(request)
    expected_contract = build_chat_contract(
        knowledge_base_id=request.knowledge_base_id,
        answer="Grounded result [source_1]",
        retrieved_documents=request.retrieved_documents,
        limit=request.limit,
        trace_id=request.trace_id,
        prompt_bundle=request.prompt_bundle,
        cited_source_ids=["source_1"],
        preprocessing_metadata=preprocessing_metadata(request.preprocessing),
    )

    # Then
    assert response is not None
    assert response.citations == expected_contract.citations
    assert response.source_chunks == expected_contract.source_chunks


def test_shared_finalizer_keeps_a_successful_answer_when_trace_update_fails():
    # Given
    request = _finalization_request(
        raw_answer="Grounded result [source_1]",
        retrieved_documents=[_document()],
        trace=FailingTrace(),
    )

    # When
    response = finalize_answer(request)

    # Then
    assert response is not None
    assert response.answer == "Grounded result [source_1]"
