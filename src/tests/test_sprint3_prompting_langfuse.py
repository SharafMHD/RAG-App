from types import SimpleNamespace
from uuid import uuid4

from helpers.config import Settings
from routes.nlp import _build_chat_contract
from services.answer_validation import no_answer_text, validate_generated_answer
from services.langfuse_service import LangfuseService
from services.prompt_service import PromptService


def test_langfuse_disabled_returns_local_trace_id():
    settings = Settings(_env_file=None, LANGFUSE_ENABLED=False)
    service = LangfuseService(settings)

    assert service.enabled is False
    assert service.client is None
    assert service.create_trace_id()


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


def test_answer_validation_repairs_missing_citation_with_top_source():
    validated = validate_generated_answer(
        "The law defines the insured person.",
        available_source_ids=["source_1", "source_2"],
        query_text="Who is insured?",
        require_citations=True,
    )

    assert validated.is_answered is True
    assert validated.cited_source_ids == ["source_1"]
    assert validated.answer.endswith("[source_1]")


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
