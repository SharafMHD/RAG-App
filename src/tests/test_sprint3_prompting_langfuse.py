from collections.abc import Mapping
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Literal
from uuid import uuid4

import pytest
from pydantic import JsonValue

from helpers.config import Settings
from routes.nlp import _generation_failure_response
from services.answer_finalization import build_chat_contract as _build_chat_contract
from services.answer_finalization import (
    should_report_generation_failure as _should_report_generation_failure,
)
from services.answer_validation import no_answer_text, validate_generated_answer
from services.langfuse_service import LangfuseService
from services.prompt_service import PromptService


@dataclass(frozen=True, slots=True)
class _ScoreCall:
    name: str
    value: float
    trace_id: str
    data_type: Literal["NUMERIC"]
    comment: str | None
    metadata: Mapping[str, JsonValue] | None


class _RecordingLangfuseClient:
    def __init__(self) -> None:
        self.score_calls: list[_ScoreCall] = []
        self.flush_calls = 0

    def create_score(
        self,
        *,
        name: str,
        value: float,
        trace_id: str,
        data_type: Literal["NUMERIC"],
        comment: str | None,
        metadata: Mapping[str, JsonValue] | None,
    ) -> None:
        self.score_calls.append(
            _ScoreCall(
                name=name,
                value=value,
                trace_id=trace_id,
                data_type=data_type,
                comment=comment,
                metadata=metadata,
            )
        )

    def flush(self) -> None:
        self.flush_calls += 1


class _LangfuseFailure(RuntimeError):
    pass


class _FailingLangfuseClient:
    def create_score(
        self,
        *,
        name: str,
        value: float,
        trace_id: str,
        data_type: Literal["NUMERIC"],
        comment: str | None,
        metadata: Mapping[str, JsonValue] | None,
    ) -> None:
        raise _LangfuseFailure


def test_langfuse_disabled_returns_local_trace_id():
    settings = Settings(_env_file=None, LANGFUSE_ENABLED=False)
    service = LangfuseService(settings)

    assert service.enabled is False
    assert service.client is None
    assert service.create_trace_id()


def test_langfuse_feedback_score_returns_disabled_without_client():
    service = LangfuseService(Settings(_env_file=None, LANGFUSE_ENABLED=False))

    assert service.score_feedback(trace_id="trace-1", rating="thumbs_up") == "disabled"


@pytest.mark.parametrize(
    ("rating", "expected_value"),
    [("thumbs_up", 1.0), ("thumbs_down", 0.0)],
)
def test_langfuse_feedback_score_forwards_rating_and_optional_fields(
    rating: Literal["thumbs_up", "thumbs_down"],
    expected_value: float,
):
    service = LangfuseService(Settings(_env_file=None, LANGFUSE_ENABLED=False))
    client = _RecordingLangfuseClient()
    service.client = client
    metadata = {"surface": "answer", "attempt": 1}

    status = service.score_feedback(
        trace_id="trace-1",
        rating=rating,
        comment="Helpful context",
        metadata=metadata,
    )

    assert status == "sent"
    assert client.score_calls == [
        _ScoreCall(
            name="answer_feedback",
            value=expected_value,
            trace_id="trace-1",
            data_type="NUMERIC",
            comment="Helpful context",
            metadata=metadata,
        )
    ]
    assert client.flush_calls == 1


def test_langfuse_feedback_score_contains_client_failure():
    service = LangfuseService(Settings(_env_file=None, LANGFUSE_ENABLED=False))
    service.client = _FailingLangfuseClient()

    assert service.score_feedback(trace_id="trace-1", rating="thumbs_down") == "failed"


def test_prompt_service_local_fallback_is_grounded_and_citation_required():
    settings = Settings(_env_file=None, LANGFUSE_ENABLED=False)
    prompt = PromptService(settings, LangfuseService(settings)).get_rag_prompt(query_text="What is RAG?")

    assert prompt.prompt_source == "local"
    assert "Answer only using the provided source chunks" in prompt.system_prompt
    assert "[source_1]" in prompt.system_prompt
    assert "What is RAG?" in prompt.footer_prompt


def test_no_answer_behavior_for_empty_retrieval_uses_query_language():
    validated = validate_generated_answer(
        "",
        available_source_ids=[],
        query_text="ما هو القانون؟",
    )

    assert validated.is_answered is False
    assert validated.confidence == 0.0
    assert validated.cited_source_ids == []
    assert "لا أملك معلومات كافية" in validated.answer


def test_answer_validation_rejects_invalid_citation_ids_in_strict_mode():
    validated = validate_generated_answer(
        "The answer is grounded [source_9].",
        available_source_ids=["source_1"],
        query_text="What is covered?",
        strict_citation_validation=True,
    )

    assert validated.is_answered is False
    assert validated.cited_source_ids == []
    assert validated.answer == no_answer_text("What is covered?")


def test_answer_validation_rejects_missing_required_citation():
    validated = validate_generated_answer(
        "The law defines the insured person.",
        available_source_ids=["source_1", "source_2"],
        query_text="Who is insured?",
        require_citations=True,
    )

    assert validated.is_answered is False
    assert validated.cited_source_ids == []
    assert validated.answer == no_answer_text("Who is insured?")


def test_generation_failure_with_retrieved_sources_is_reported_as_error():
    retrieved_documents = [SimpleNamespace(text="grounded source")]

    assert _should_report_generation_failure(None, retrieved_documents) is True
    assert _should_report_generation_failure("   ", retrieved_documents) is True
    assert _should_report_generation_failure("Answer [source_1]", retrieved_documents) is False
    assert _should_report_generation_failure(None, []) is False

    response = _generation_failure_response(uuid4())

    assert response.status_code == 502


def test_chat_contract_includes_prompt_metadata_and_filters_citations():
    document = SimpleNamespace(
        text="source text",
        score=0.7,
        chunk_id="chunk-1",
        page_number=3,
        metadata={"document_name": "doc.pdf"},
        retrieval_mode="hybrid",
    )
    prompt_bundle = SimpleNamespace(
        prompt_name="rag-grounded-answer",
        prompt_version="7",
        prompt_source="langfuse",
    )

    response = _build_chat_contract(
        knowledge_base_id=uuid4(),
        answer="Answer [source_1]",
        retrieved_documents=[document],
        limit=5,
        trace_id="trace-1",
        prompt_bundle=prompt_bundle,
        cited_source_ids=["source_1"],
    )

    assert response.trace_id == "trace-1"
    assert response.citations[0].source_id == "source_1"
    assert response.retrieval_metadata.strategy == "hybrid"
    assert response.retrieval_metadata.prompt_name == "rag-grounded-answer"
    assert response.retrieval_metadata.prompt_version == "7"
    assert response.retrieval_metadata.prompt_source == "langfuse"
