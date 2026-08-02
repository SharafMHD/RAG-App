from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID, uuid4

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from helpers.config import Settings
from models.db_schemes import RetrievedDocuments
from routes import nlp as nlp_routes
from routes.schemes.nlp import AnswerStreamEvent, SearchRequest
from services.prompt_service import PromptBundle
from services.query_preprocessing import QueryPreprocessingMetadata
from stores.llm.LLMInterface import LLMStreamingError, LLMStreamingUnsupportedError


class RecordingIterator:
    def __init__(
        self,
        tokens: list[str | int | None] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.tokens = tokens if tokens is not None else []
        self.error = error
        self.index = 0
        self.close_calls = 0

    def __iter__(self) -> Iterator[str | int | None]:
        return self

    def __next__(self) -> str | int | None:
        if self.error is not None:
            raise self.error
        if self.index == len(self.tokens):
            raise StopIteration
        token = self.tokens[self.index]
        self.index += 1
        return token

    def close(self) -> None:
        self.close_calls += 1


class GenerationClient:
    def __init__(self, iterator: RecordingIterator) -> None:
        self.iterator = iterator
        self.stream_calls = 0

    def generate_text_stream(self, prompt: str, chat_history: list[dict[str, str]]) -> RecordingIterator:
        self.stream_calls += 1
        return self.iterator


class RecordingLangfuseService:
    def create_trace_id(self) -> str:
        return "trace-stream"

    @contextmanager
    def trace_answer(self, trace_id: str, *, input, metadata):
        yield SimpleNamespace(update=lambda **kwargs: None)


class KnowledgeBaseModel:
    async def get_knowledge_base_or_create(self, knowledge_base_id: UUID):
        return SimpleNamespace(knowledge_base_id=knowledge_base_id)


class AnswerController:
    preparation = None

    def __init__(self, **kwargs) -> None:
        pass

    async def prepare_rag_answer(self, **kwargs):
        return self.preparation


class Request:
    def __init__(self, app, disconnect_after_checks: int | None = None) -> None:
        self.app = app
        self.disconnect_after_checks = disconnect_after_checks
        self.disconnect_checks = 0

    async def is_disconnected(self) -> bool:
        self.disconnect_checks += 1
        if self.disconnect_after_checks is None:
            return False
        return self.disconnect_checks > self.disconnect_after_checks


def _document() -> RetrievedDocuments:
    return RetrievedDocuments(
        text="Grounded source text",
        score=0.8,
        chunk_id="chunk-1",
        page_number=4,
        metadata={"document_name": "policy.pdf"},
        retrieval_mode="hybrid",
    )


def _preparation(
    documents: list[RetrievedDocuments] | None = None,
    *,
    chat_history: list[dict[str, str]] | None = None,
):
    return SimpleNamespace(
        full_prompt="full prompt",
        chat_history=chat_history if chat_history is not None else [{"role": "system", "content": "system prompt"}],
        retrieved_documents=documents if documents is not None else [_document()],
        prompt_bundle=PromptBundle(
            system_prompt="system prompt",
            footer_prompt="footer prompt",
            prompt_name="rag-grounded-answer",
            prompt_version="1",
            prompt_source="local",
        ),
        preprocessing=QueryPreprocessingMetadata(
            status="disabled",
            original_query="What is covered?",
            generated_queries=(),
        ),
    )


def _install_route_fakes(monkeypatch, preparation) -> None:
    async def create_instance(**kwargs):
        return KnowledgeBaseModel()

    AnswerController.preparation = preparation
    monkeypatch.setattr(nlp_routes.KnowledgeBaseDataModel, "create_instance", create_instance)
    monkeypatch.setattr(nlp_routes, "NLPController", AnswerController)


def _fake_app(iterator: RecordingIterator):
    return SimpleNamespace(
        db_client=None,
        generation_client=GenerationClient(iterator),
        embedding_client=SimpleNamespace(),
        vector_db_client=SimpleNamespace(),
        template_parser=SimpleNamespace(),
        langfuse_service=RecordingLangfuseService(),
        prompt_service=SimpleNamespace(),
    )


def _fastapi_app(iterator: RecordingIterator) -> FastAPI:
    app = FastAPI()
    fake_app = _fake_app(iterator)
    for name in (
        "db_client",
        "generation_client",
        "embedding_client",
        "vector_db_client",
        "template_parser",
        "langfuse_service",
        "prompt_service",
    ):
        setattr(app, name, getattr(fake_app, name))
    app.include_router(nlp_routes.nlp_router)
    app.dependency_overrides[nlp_routes.get_settings] = lambda: Settings(
        _env_file=None, LANGFUSE_ENABLED=False
    )
    return app


async def _collect(response) -> tuple[str, list[AnswerStreamEvent]]:
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    wire = "".join(chunks)
    adapter = TypeAdapter(AnswerStreamEvent)
    frames = []
    for frame in wire.split("\n\n"):
        if frame:
            event_line, data_line = frame.split("\n")
            frames.append(
                adapter.validate_python(
                    {
                        "event": event_line.removeprefix("event: "),
                        "data": json.loads(data_line.removeprefix("data: ")),
                    }
                )
            )
    return wire, frames


async def _invoke_and_collect(request: Request):
    response = await nlp_routes.answer_rag_stream(
        request,
        uuid4(),
        SearchRequest(text="What is covered?", limit=5, strategy="hybrid"),
        Settings(_env_file=None, LANGFUSE_ENABLED=False),
    )
    wire, frames = await _collect(response)
    return response, wire, frames


def test_stream_route_exists_and_uses_sse_content_type(monkeypatch):
    # Given
    iterator = RecordingIterator(["answer"])
    _install_route_fakes(monkeypatch, _preparation())
    app = _fastapi_app(iterator)
    path = "/api/v1/nlp/index/answer/{knowledge_base_id}/stream"

    # When
    with TestClient(app) as client:
        response = client.post(
            path.replace("{knowledge_base_id}", str(uuid4())),
            json={"text": "What is covered?", "limit": 5, "strategy": "hybrid"},
        )

    # Then
    assert path in {route.path for route in app.routes}
    assert response.headers["content-type"].startswith("text/event-stream")


@pytest.mark.parametrize(
    "chat_history",
    [[{"role": "system", "content": "system prompt"}], []],
)
def test_stream_route_emits_tokens_then_validated_final_then_done(monkeypatch, chat_history):
    # Given
    iterator = RecordingIterator(["provisional ", "answer"])
    _install_route_fakes(monkeypatch, _preparation(chat_history=chat_history))
    request = Request(_fake_app(iterator))

    # When
    _, _, frames = anyio.run(_invoke_and_collect, request)

    # Then
    assert [frame.event for frame in frames] == ["token", "token", "final", "done"]
    assert [frame.model_dump()["data"]["content"] for frame in frames[:2]] == [
        "provisional ",
        "answer",
    ]
    assert frames[2].model_dump()["data"]["response"]["answer"] == (
        "provisional answer [source_1]"
    )
    assert iterator.close_calls == 1


def test_stream_route_no_results_emits_final_done_without_provider(monkeypatch):
    # Given
    iterator = RecordingIterator()
    _install_route_fakes(monkeypatch, _preparation([]))
    app = _fake_app(iterator)

    # When
    _, _, frames = anyio.run(_invoke_and_collect, Request(app))

    # Then
    assert [frame.event for frame in frames] == ["final", "done"]
    assert frames[0].model_dump()["data"]["response"]["citations"] == []
    assert app.generation_client.stream_calls == 0


@pytest.mark.parametrize(
    ("error", "detail"),
    [
        (LLMStreamingUnsupportedError("unsupported"), "streaming_unsupported"),
        (LLMStreamingError("provider failed"), "provider_error"),
        (RuntimeError("unexpected provider failure"), "internal_error"),
    ],
)
def test_stream_route_provider_failures_emit_error_then_done(monkeypatch, error, detail):
    # Given
    _install_route_fakes(monkeypatch, _preparation())
    request = Request(_fake_app(RecordingIterator(error=error)))

    # When
    _, _, frames = anyio.run(_invoke_and_collect, request)

    # Then
    assert [frame.event for frame in frames] == ["error", "done"]
    assert frames[0].model_dump()["data"]["detail"] == detail


def test_stream_route_blank_output_after_documents_emits_error_then_done(monkeypatch):
    # Given
    _install_route_fakes(monkeypatch, _preparation())
    request = Request(_fake_app(RecordingIterator()))

    # When
    _, _, frames = anyio.run(_invoke_and_collect, request)

    # Then
    assert [frame.event for frame in frames] == ["error", "done"]
    assert frames[0].model_dump()["data"]["detail"] == "generation_error"


def test_stream_route_invalid_token_emits_error_then_done(monkeypatch):
    # Given
    _install_route_fakes(monkeypatch, _preparation())
    request = Request(_fake_app(RecordingIterator([3])))

    # When
    _, _, frames = anyio.run(_invoke_and_collect, request)

    # Then
    assert [frame.event for frame in frames] == ["error", "done"]
    assert frames[0].model_dump()["data"]["detail"] == "invalid_token"


def test_stream_route_invalid_uuid_or_body_remains_normal_422():
    # Given
    app = _fastapi_app(RecordingIterator())

    # When
    with TestClient(app) as client:
        invalid_uuid = client.post(
            "/api/v1/nlp/index/answer/not-a-uuid/stream",
            json={"text": "query"},
        )
        invalid_body = client.post(
            f"/api/v1/nlp/index/answer/{uuid4()}/stream",
            json={"text": "   "},
        )

    # Then
    assert invalid_uuid.status_code == 422
    assert invalid_body.status_code == 422


def test_stream_route_json_escapes_newline_token_on_one_data_line(monkeypatch):
    # Given
    _install_route_fakes(monkeypatch, _preparation())
    request = Request(_fake_app(RecordingIterator(["first line\nsecond line"])))

    # When
    _, wire, frames = anyio.run(_invoke_and_collect, request)

    # Then
    token_frame = wire.split("\n\n")[0]
    assert token_frame.count("\n") == 1
    assert "\\n" in token_frame
    assert frames[0].model_dump()["data"]["content"] == "first line\nsecond line"


def test_stream_route_disconnect_closes_provider_without_terminal_frames(monkeypatch):
    # Given
    iterator = RecordingIterator(["first", "second"])
    _install_route_fakes(monkeypatch, _preparation())
    app = _fake_app(iterator)

    # When
    _, wire, frames = anyio.run(
        _invoke_and_collect,
        Request(app, disconnect_after_checks=1),
    )

    # Then
    assert wire == ""
    assert frames == []
    assert app.generation_client.stream_calls == 1
    assert iterator.close_calls == 1
