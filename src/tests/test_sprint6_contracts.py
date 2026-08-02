import pytest
from pydantic import TypeAdapter, ValidationError

from routes.schemes.nlp import (
    AnswerStreamEvent,
    ChatAnswerResponse,
    FeedbackRequest,
    FeedbackResponse,
    SearchRequest,
)


def test_legacy_answer_payloads_are_valid_when_sprint6_fields_are_omitted():
    # Given
    request = SearchRequest(text="What does the document say?", limit=5, strategy="hybrid")
    response = ChatAnswerResponse(
        knowledge_base_id="kb-1",
        answer="RAG combines retrieval and generation.",
        retrieval_metadata={
            "strategy": "hybrid",
            "requested_top_k": 5,
            "returned_count": 0,
        },
        trace_id="trace-1",
        message="ok",
    )

    # When
    payload = response.model_dump()

    # Then
    assert request.preprocessing is None
    assert request.limit == 5
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


def test_search_request_rejects_unknown_top_level_fields():
    # Given
    request_payload = {"text": "query", "api_key": "must-not-be-accepted"}

    # When / Then
    with pytest.raises(ValidationError):
        SearchRequest.model_validate(request_payload)


def test_search_request_rejects_string_limit_coercion():
    # Given
    request_payload = {"text": "query", "limit": "5"}

    # When / Then
    with pytest.raises(ValidationError):
        SearchRequest.model_validate(request_payload)


def test_sse_event_payloads_are_valid_when_well_formed():
    # Given
    event_adapter = TypeAdapter(AnswerStreamEvent)
    final_response = {
        "knowledge_base_id": "kb-1",
        "answer": "Validated answer [source_1]",
        "retrieval_metadata": {
            "strategy": "vector",
            "requested_top_k": 5,
            "returned_count": 0,
        },
        "trace_id": "trace-1",
        "message": "ok",
    }

    # When
    token_event = event_adapter.validate_python({"event": "token", "data": {"content": "Validated "}})
    final_event = event_adapter.validate_python({"event": "final", "data": {"response": final_response}})
    error_event = event_adapter.validate_python(
        {"event": "error", "data": {"detail": "provider_error", "message": "Generation failed"}}
    )
    done_event = event_adapter.validate_python({"event": "done", "data": {}})

    # Then
    assert token_event.data.content == "Validated "
    assert final_event.data.response.answer == "Validated answer [source_1]"
    assert error_event.data.detail == "provider_error"
    assert done_event.event == "done"


@pytest.mark.parametrize(
    "event_payload",
    [
        {"event": "metadata", "data": {}},
        {"event": "token", "data": {"content": ""}},
        {"event": "token", "data": {"content": ["not a token"]}},
        {"event": "token", "data": {"content": "token", "unexpected": True}},
        {"event": "final", "data": {}},
        {"event": "error", "data": {"message": "Generation failed"}},
        {"event": "error", "data": {"detail": "provider_error", "message": ""}},
        {"event": "done", "data": {"unexpected": True}},
    ],
)
def test_sse_event_payloads_are_rejected_when_malformed(event_payload):
    # Given
    event_adapter = TypeAdapter(AnswerStreamEvent)

    # When / Then
    with pytest.raises(ValidationError):
        event_adapter.validate_python(event_payload)


def test_feedback_payloads_are_valid_when_feedback_is_complete():
    # Given
    request = FeedbackRequest(
        trace_id="trace-1",
        knowledge_base_id="kb-1",
        rating="thumbs_up",
        comment="Helpful answer.",
        question="What is RAG?",
        answer="RAG combines retrieval and generation.",
        citations=[],
        source_chunks=[],
    )

    # When
    response = FeedbackResponse(
        trace_id=request.trace_id,
        rating=request.rating,
        comment=request.comment,
        message="Feedback saved.",
    )

    # Then
    assert response.status is True
    assert response.rating == "thumbs_up"


@pytest.mark.parametrize(
    "feedback_payload",
    [
        {
            "trace_id": "trace-1",
            "knowledge_base_id": "kb-1",
            "rating": "neutral",
            "question": "What is RAG?",
            "answer": "An answer.",
        },
        {
            "trace_id": "trace-1",
            "knowledge_base_id": "kb-1",
            "rating": "thumbs_down",
            "comment": "x" * 2001,
            "question": "What is RAG?",
            "answer": "An answer.",
        },
    ],
)
def test_feedback_payloads_are_rejected_when_rating_or_comment_is_malformed(feedback_payload):
    # Given / When / Then
    with pytest.raises(ValidationError):
        FeedbackRequest.model_validate(feedback_payload)


@pytest.mark.parametrize(
    "feedback_payload",
    [
        {
            "trace_id": "   ",
            "knowledge_base_id": "kb-1",
            "rating": "thumbs_up",
            "question": "What is RAG?",
            "answer": "An answer.",
        },
        {
            "trace_id": "trace-1",
            "knowledge_base_id": "   ",
            "rating": "thumbs_up",
            "question": "What is RAG?",
            "answer": "An answer.",
        },
        {
            "trace_id": "trace-1",
            "knowledge_base_id": "kb-1",
            "rating": "thumbs_up",
            "question": "   ",
            "answer": "An answer.",
        },
        {
            "trace_id": "trace-1",
            "knowledge_base_id": "kb-1",
            "rating": "thumbs_up",
            "question": "What is RAG?",
            "answer": "   ",
        },
        {
            "trace_id": "trace-1",
            "knowledge_base_id": "kb-1",
            "rating": "thumbs_up",
            "question": "What is RAG?",
            "answer": "An answer.",
            "api_key": "must-not-be-accepted",
        },
        {
            "trace_id": "trace-1",
            "knowledge_base_id": "kb-1",
            "rating": "thumbs_up",
            "question": "What is RAG?",
            "answer": "An answer.",
            "citations": [{"source_id": "source_1", "rank": 1, "api_key": "must-not-be-accepted"}],
        },
        {
            "trace_id": "trace-1",
            "knowledge_base_id": "kb-1",
            "rating": "thumbs_up",
            "question": "What is RAG?",
            "answer": "An answer.",
            "source_chunks": [{"source_id": "source_1", "rank": 1, "text": "snapshot", "full_prompt": "must-not-be-accepted"}],
        },
    ],
)
def test_feedback_payloads_are_rejected_when_blank_or_secret_bearing(feedback_payload):
    # Given / When / Then
    with pytest.raises(ValidationError):
        FeedbackRequest.model_validate(feedback_payload)


def test_preprocessing_payloads_are_valid_when_opted_in():
    # Given
    request_payload = {
        "text": "Compare the policy requirements.",
        "limit": 5,
        "strategy": "hybrid",
        "preprocessing": {
            "expand": True,
            "decompose": True,
            "max_generated_queries": 4,
        },
    }

    # When
    request = SearchRequest.model_validate(request_payload)

    # Then
    assert request.preprocessing is not None
    assert request.preprocessing.expand is True
    assert request.preprocessing.decompose is True
    assert request.preprocessing.max_generated_queries == 4


@pytest.mark.parametrize(
    "request_payload",
    [
        {"text": "   "},
        {"text": "query", "preprocessing": {"max_generated_queries": 0}},
        {"text": "query", "preprocessing": {"max_generated_queries": 11}},
        {"text": "query", "preprocessing": {"expand": "true"}},
        {"text": "query", "preprocessing": {"decompose": 1}},
        {"text": "query", "preprocessing": {"expand": True, "unexpected": True}},
    ],
)
def test_search_request_is_rejected_when_query_or_preprocessing_limit_is_malformed(request_payload):
    # Given / When / Then
    with pytest.raises(ValidationError):
        SearchRequest.model_validate(request_payload)
