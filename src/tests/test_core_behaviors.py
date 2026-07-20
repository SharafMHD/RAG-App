import pytest
from pydantic import ValidationError

from helpers.config import Settings
from controllers.DataController import DataController
from controllers.ProcessFileController import ProcessFileController
from routes.schemes.data import KnowledgeBaseData
from routes.schemes.nlp import ChatAnswerResponse, SearchRequest
from stores.llm.Templates.template_parser import TemplateParser


def test_search_request_rejects_blank_text():
    with pytest.raises(ValueError):
        SearchRequest(text="   ")


def test_search_request_validates_limit_bounds():
    with pytest.raises(ValueError):
        SearchRequest(text="query", limit=0)


def test_knowledge_base_data_strips_name_and_defaults_owner():
    knowledge_base_data = KnowledgeBaseData(knowledge_base_name="  demo  ")

    assert knowledge_base_data.knowledge_base_name == "demo"
    assert knowledge_base_data.owner == "system"


def test_template_parser_falls_back_to_default_language():
    parser = TemplateParser(language="missing", default_language="en")

    prompt = parser.get_template_module("rag", "footer_prompt", {"query_text": "What is RAG?"})

    assert "What is RAG?" in prompt
    assert "## Answer:" in prompt


def test_settings_accept_legacy_file_env_names_and_normalizes_enums():
    settings = Settings(
        _env_file=None,
        FILE_ALLWOED_TYPES=["text/plain"],
        FILE_ALLOWED_SZIE=5,
        GENERATION_BACKEND="openai",
        EMBEDDING_BACKEND="cohere",
        VECTOR_DB_BACKEND="pgvector",
        VECTOR_DB_DISTANCE_METHOD="cosine",
    )

    assert settings.FILE_ALLOWED_TYPES == ["text/plain"]
    assert settings.FILE_ALLOWED_SIZE == 5
    assert settings.GENERATION_BACKEND == "OPENAI"
    assert settings.EMBEDDING_BACKEND == "COHERE"
    assert settings.VECTOR_DB_BACKEND == "PGVECTOR"
    assert settings.VECTOR_DB_DISTANCE_METHOD == "COSINE"


def test_settings_reject_invalid_chunk_overlap():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, FILE_DEFAULT_CHUNK_SIZE=10, FILE_OVERLAP_SIZE=10)


def test_upload_filename_is_sanitized_and_basenamed():
    controller = DataController.__new__(DataController)

    assert controller.get_clean_filename("../../bad name?.pdf") == "bad_name_.pdf"


def test_chat_answer_contract_matches_frontend_shape():
    response = ChatAnswerResponse(
        knowledge_base_id="kb-1",
        answer="RAG combines retrieval and generation.",
        citations=[],
        source_chunks=[],
        confidence=0.8,
        retrieval_metadata={
            "strategy": "vector",
            "requested_top_k": 5,
            "returned_count": 0,
            "vector_top_k": 5,
        },
        trace_id="trace-1",
        message="ok",
    )

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
    assert payload["retrieval_metadata"]["strategy"] == "vector"


def test_simple_splitter_respects_overlap():
    controller = ProcessFileController.__new__(ProcessFileController)

    chunks = controller.process_doc_simple_splitter(
        text=["abcdefghij"],
        chunk_size=4,
        overlap_size=1,
        metadata=[{"source": "unit-test"}],
    )

    assert [chunk.page_content for chunk in chunks] == ["abcd", "defg", "ghij"]
    assert chunks[0].metadata == {"source_documents": [{"source": "unit-test"}]}
