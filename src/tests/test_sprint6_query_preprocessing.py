from __future__ import annotations

import anyio

from controllers.NLPController import NLPController
from helpers.config import Settings
from models.db_schemes import RetrievedDocuments
from services.query_preprocessing import (
    QueryGenerationMode,
    QueryPreprocessingOptions,
    QueryPreprocessingSelection,
    QueryPreprocessingService,
)


class RecordingGenerator:
    def __init__(self, responses: dict[tuple[QueryGenerationMode, str], tuple[str, ...]]):
        self.responses = responses
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        return self.responses[(request.mode, request.source_query)]


class FailingGenerator:
    async def generate(self, request):
        raise RuntimeError("generation failed")


class GenerationClient:
    class enums:
        SYSTEM = type("System", (), {"value": "system"})()

    def process_text(self, text):
        return text

    def construct_prompt(self, prompt, role):
        return {"prompt": prompt, "role": role}

    def generate_text(self, prompt, chat_history):
        return "Grounded answer [source_1]"


class RecordingController(NLPController):
    def __init__(self, settings, query_preprocessor):
        super().__init__(None, GenerationClient(), None, None, settings=settings, query_preprocessor=query_preprocessor)
        self.seen_queries = []

    async def search_vector(self, knowledge_base, text, limit=5):
        self.seen_queries.append(text)
        return [RetrievedDocuments(text=text, score=1.0, chunk_id=text, retrieval_mode="vector")]


def _options(*, expand=False, decompose=False, max_generated_queries=3):
    return QueryPreprocessingOptions(
        expand=expand,
        decompose=decompose,
        max_generated_queries=max_generated_queries,
        timeout_seconds=1.0,
        max_output_tokens=32,
    )


def test_preprocessor_is_a_default_noop_when_both_operations_are_disabled():
    # Given
    generator = RecordingGenerator({})
    service = QueryPreprocessingService(generator)

    # When
    prepared = anyio.run(service.prepare, "Original query", _options())

    # Then
    assert prepared.queries == ("Original query",)
    assert prepared.metadata.status == "disabled"
    assert generator.requests == []


def test_settings_disable_preprocessing_by_default():
    # Given
    settings = Settings(_env_file=None)

    # When
    options = QueryPreprocessingOptions.from_settings(settings)

    # Then
    assert options.expand is False
    assert options.decompose is False


def test_settings_enable_hybrid_retrieval_by_default():
    # Given
    settings = Settings(_env_file=None)

    # Then
    assert settings.HYBRID_SEARCH_ENABLED is True


def test_preprocessor_adds_expansions_while_retaining_the_original_query():
    # Given
    generator = RecordingGenerator({
        (QueryGenerationMode.EXPAND, "Original query"): ("related query", "alternate wording"),
    })
    service = QueryPreprocessingService(generator)

    # When
    prepared = anyio.run(service.prepare, "Original query", _options(expand=True))

    # Then
    assert prepared.queries == ("Original query", "related query", "alternate wording")
    assert prepared.metadata.status == "applied"


def test_preprocessor_uses_decomposition_without_expansion_when_requested():
    # Given
    generator = RecordingGenerator({
        (QueryGenerationMode.DECOMPOSE, "Original query"): ("first part", "second part"),
    })
    service = QueryPreprocessingService(generator)

    # When
    prepared = anyio.run(service.prepare, "Original query", _options(decompose=True))

    # Then
    assert prepared.queries == ("Original query", "first part", "second part")
    assert [request.mode for request in generator.requests] == [QueryGenerationMode.DECOMPOSE]


def test_preprocessor_decomposes_before_expanding_each_subquery():
    # Given
    generator = RecordingGenerator({
        (QueryGenerationMode.DECOMPOSE, "Original query"): ("part one", "part two"),
        (QueryGenerationMode.EXPAND, "part one"): ("part one alternative",),
        (QueryGenerationMode.EXPAND, "part two"): ("part two alternative",),
    })
    service = QueryPreprocessingService(generator)

    # When
    prepared = anyio.run(service.prepare, "Original query", _options(expand=True, decompose=True, max_generated_queries=4))

    # Then
    assert prepared.queries == ("Original query", "part one", "part two", "part one alternative", "part two alternative")
    assert [(request.mode, request.source_query) for request in generator.requests] == [
        (QueryGenerationMode.DECOMPOSE, "Original query"),
        (QueryGenerationMode.EXPAND, "part one"),
        (QueryGenerationMode.EXPAND, "part two"),
    ]


def test_preprocessor_normalizes_and_deduplicates_generated_queries():
    # Given
    generator = RecordingGenerator({
        (QueryGenerationMode.EXPAND, "Original query"): ("  Related   query ", "related query", "ORIGINAL QUERY", ""),
    })
    service = QueryPreprocessingService(generator)

    # When
    prepared = anyio.run(service.prepare, "Original query", _options(expand=True))

    # Then
    assert prepared.queries == ("Original query", "Related query")
    assert prepared.metadata.generated_queries == ("Related query",)


def test_preprocessor_deduplicates_against_normalized_original_query():
    # Given
    generator = RecordingGenerator({
        (QueryGenerationMode.EXPAND, "Original   query"): ("original query",),
    })
    service = QueryPreprocessingService(generator)

    # When
    prepared = anyio.run(service.prepare, "Original   query", _options(expand=True))

    # Then
    assert prepared.queries == ("Original   query",)
    assert prepared.metadata.generated_queries == ()


def test_preprocessor_caps_generated_queries_before_retrieval_fanout():
    # Given
    generator = RecordingGenerator({
        (QueryGenerationMode.EXPAND, "Original query"): ("one", "two", "three"),
    })
    service = QueryPreprocessingService(generator)

    # When
    prepared = anyio.run(service.prepare, "Original query", _options(expand=True, max_generated_queries=2))

    # Then
    assert prepared.queries == ("Original query", "one", "two")
    assert prepared.metadata.generated_query_count == 2


def test_preprocessor_falls_back_to_original_query_when_generation_fails():
    # Given
    service = QueryPreprocessingService(FailingGenerator())

    # When
    prepared = anyio.run(service.prepare, "Original query", _options(expand=True))

    # Then
    assert prepared.queries == ("Original query",)
    assert prepared.metadata.status == "fallback"


def test_search_index_keeps_disabled_retrieval_on_the_original_query():
    # Given
    generator = RecordingGenerator({})
    controller = RecordingController(Settings(_env_file=None), QueryPreprocessingService(generator))

    # When
    result = anyio.run(controller.search_index_with_metadata, None, "Original query", 3, "vector", None)

    # Then
    assert [document.text for document in result.documents] == ["Original query"]
    assert controller.seen_queries == ["Original query"]
    assert result.preprocessing.status == "disabled"


def test_answer_rag_query_preserves_the_legacy_tuple_when_preprocessing_is_omitted():
    # Given
    controller = RecordingController(Settings(_env_file=None), QueryPreprocessingService(RecordingGenerator({})))

    # When
    response = anyio.run(controller.answer_rag_query, None, "Original query", 3, "vector", None)

    # Then
    assert len(response) == 5


def test_search_index_uses_existing_fusion_and_exposes_preprocessing_metadata():
    # Given
    generator = RecordingGenerator({
        (QueryGenerationMode.EXPAND, "Original query"): ("related query",),
    })
    controller = RecordingController(Settings(_env_file=None), QueryPreprocessingService(generator))
    selection = QueryPreprocessingSelection(expand=True, decompose=False, max_generated_queries=1)

    # When
    result = anyio.run(controller.search_index_with_metadata, None, "Original query", 3, "vector", selection)

    # Then
    assert controller.seen_queries == ["Original query", "related query"]
    assert result.documents[0].retrieval_mode == "hybrid"
    assert result.preprocessing.original_query == "Original query"
    assert result.preprocessing.generated_queries == ("related query",)


def test_search_index_falls_back_to_original_retrieval_with_metadata_when_generation_fails():
    # Given
    controller = RecordingController(Settings(_env_file=None), QueryPreprocessingService(FailingGenerator()))
    selection = QueryPreprocessingSelection(expand=True, decompose=False, max_generated_queries=1)

    # When
    result = anyio.run(controller.search_index_with_metadata, None, "Original query", 3, "vector", selection)

    # Then
    assert controller.seen_queries == ["Original query"]
    assert result.preprocessing.status == "fallback"


def test_answer_rag_query_returns_the_preprocessing_metadata_for_the_final_response():
    # Given
    generator = RecordingGenerator({
        (QueryGenerationMode.EXPAND, "Original query"): ("related query",),
    })
    controller = RecordingController(Settings(_env_file=None), QueryPreprocessingService(generator))
    selection = QueryPreprocessingSelection(expand=True, decompose=False, max_generated_queries=1)

    # When
    answer, _, _, _, _, preprocessing = anyio.run(
        controller.answer_rag_query_with_metadata,
        None,
        "Original query",
        3,
        "vector",
        selection,
    )

    # Then
    assert answer == "Grounded answer [source_1]"
    assert preprocessing.status == "applied"
    assert preprocessing.generated_queries == ("related query",)


def test_answer_rag_query_rejects_length_truncated_generation():
    # Given
    controller = RecordingController(Settings(_env_file=None), QueryPreprocessingService(RecordingGenerator({})))
    controller.generation_client.last_generation_finish_reason = "length"

    # When
    answer, _, _, _, _, _ = anyio.run(
        controller.answer_rag_query_with_metadata,
        None,
        "Original query",
        3,
        "vector",
        None,
    )

    # Then
    assert answer is None
