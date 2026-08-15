from types import SimpleNamespace

import pytest

from stores.llm.LLMInterface import (
    LLMStreamingError,
    LLMStreamingUnsupportedError,
)
from stores.llm.Providers.CoHereProvider import CoHereProvider
from stores.llm.Providers.OpenAIProvider import OpenAIProvider


class FakeIterable:
    def __init__(self, items=None, error=None):
        self.items = items or []
        self.error = error

    def __iter__(self):
        if self.error:
            raise self.error
        return iter(self.items)


class FakeOpenAICompletions:
    def __init__(self, stream):
        self.stream = stream
        self.kwargs = {}
        self.create_error = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.create_error:
            raise self.create_error
        return self.stream


class FakeOpenAIClient:
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)


def openai_chunk(content=None, *, choices=True, delta=True, finish_reason=None):
    if not choices:
        return SimpleNamespace(choices=[])
    choice = SimpleNamespace()
    choice.finish_reason = finish_reason
    if delta:
        choice.delta = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[choice])


def make_openai_provider(stream, model="gpt-4o"):
    provider = OpenAIProvider(api_key="test-key", default_generation_temperature=0.25)
    provider.set_genration_model(model)
    completions = FakeOpenAICompletions(stream)
    provider.client = FakeOpenAIClient(completions)
    return provider, completions


def test_openai_stream_yields_ordered_native_deltas_and_request_options():
    stream = FakeIterable([openai_chunk("Hel"), openai_chunk("lo")])
    provider, completions = make_openai_provider(stream)

    tokens = list(
        provider.generate_text_stream(
            "current question",
            [{"role": "system", "content": "context"}],
            max_output_tokens=42,
            temperature=0.6,
        )
    )

    assert tokens == ["Hel", "lo"]
    assert completions.kwargs == {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": "context"},
            {"role": "user", "content": "current question"},
        ],
        "max_completion_tokens": 42,
        "temperature": 0.6,
        "stream": True,
    }


def test_openai_stream_skips_empty_or_missing_delta_content():
    stream = FakeIterable(
        [
            openai_chunk("first"),
            openai_chunk("", choices=True),
            openai_chunk(None),
            openai_chunk("ignored", choices=False),
            openai_chunk("ignored", delta=False),
            openai_chunk("second"),
        ]
    )
    provider, _ = make_openai_provider(stream)

    assert list(provider.generate_text_stream("question")) == ["first", "second"]


def test_openai_empty_stream_yields_no_tokens():
    provider, _ = make_openai_provider(FakeIterable([]))

    assert list(provider.generate_text_stream("question")) == []


def test_openai_stream_rejects_length_truncated_completion():
    stream = FakeIterable([openai_chunk("partial"), openai_chunk(finish_reason="length")])
    provider, _ = make_openai_provider(stream)

    with pytest.raises(LLMStreamingError, match="OpenAI token streaming was truncated"):
        list(provider.generate_text_stream("question"))

    assert provider.last_generation_finish_reason == "length"


def test_openai_stream_retries_after_length_before_yielding_tokens():
    first_stream = FakeIterable([openai_chunk("partial"), openai_chunk(finish_reason="length")])
    second_stream = FakeIterable([openai_chunk("complete"), openai_chunk(" answer"), openai_chunk(finish_reason="stop")])
    completions = FakeOpenAICompletions(first_stream)
    provider = OpenAIProvider(api_key="test-key")
    provider.set_genration_model("gpt-4o")
    provider.client = FakeOpenAIClient(completions)

    def create(**kwargs):
        completions.kwargs = kwargs
        completions.kwargs_history.append(kwargs)
        return first_stream if len(completions.kwargs_history) == 1 else second_stream

    completions.kwargs_history = []
    completions.create = create

    assert list(provider.generate_text_stream("question", max_output_tokens=10)) == ["complete", " answer"]
    assert [call["max_completion_tokens"] for call in completions.kwargs_history] == [10, 20]
    assert provider.last_generation_finish_reason == "stop"


@pytest.mark.parametrize("failure", [RuntimeError("create failed"), ValueError("iterate failed")])
def test_openai_streaming_failures_are_typed(failure):
    stream = FakeIterable(error=failure) if isinstance(failure, ValueError) else FakeIterable([])
    provider, completions = make_openai_provider(stream)
    if isinstance(failure, RuntimeError):
        completions.create_error = failure

    with pytest.raises(LLMStreamingError, match="OpenAI token streaming failed") as raised:
        list(provider.generate_text_stream("question"))

    assert raised.value.__cause__ is failure


def test_openai_stream_missing_client_or_model_is_typed():
    provider = OpenAIProvider(api_key="test-key")
    provider.client = None

    with pytest.raises(LLMStreamingError, match="OpenAI client was not set"):
        list(provider.generate_text_stream("question"))

    provider.client = SimpleNamespace()
    with pytest.raises(LLMStreamingError, match="OpenAI generation model was not set"):
        list(provider.generate_text_stream("question"))


class FakeCohereClient:
    def __init__(self, events=None, error=None):
        self.events = events or []
        self.error = error
        self.kwargs = {}

    def chat_stream(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.events


class FakeCohereGenerateClient:
    def __init__(self):
        self.kwargs = {}

    def chat(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(message=SimpleNamespace(content=[SimpleNamespace(text="legacy answer")]))


def cohere_content_event(text=None):
    return SimpleNamespace(
        type="content-delta",
        delta=SimpleNamespace(
            message=SimpleNamespace(content=SimpleNamespace(text=text))
        ),
    )


def test_cohere_stream_yields_ordered_content_deltas_and_v2_messages():
    provider = CoHereProvider(api_key="test-key", default_generation_temperature=0.2)
    provider.set_genration_model("command-r")
    client = FakeCohereClient(
        events=[cohere_content_event("Hel"), cohere_content_event("lo")]
    )
    provider.client = client

    tokens = list(
        provider.generate_text_stream(
            "current question",
            [{"role": "SYSTEM", "text": "context"}],
            max_output_tokens=42,
            temperature=0.6,
        )
    )

    assert tokens == ["Hel", "lo"]
    assert client.kwargs == {
        "model": "command-r",
        "messages": [
            {"role": "system", "content": "context"},
            {"role": "user", "content": "current question"},
        ],
        "temperature": 0.6,
        "max_tokens": 42,
    }
    assert "message" not in client.kwargs
    assert "chat_history" not in client.kwargs


def test_cohere_stream_skips_lifecycle_and_empty_events():
    lifecycle = SimpleNamespace(type="message-start")
    missing_delta = SimpleNamespace(type="content-delta")
    stream = [
        lifecycle,
        cohere_content_event("first"),
        cohere_content_event(""),
        cohere_content_event(None),
        missing_delta,
        cohere_content_event("second"),
    ]
    provider = CoHereProvider(api_key="test-key")
    provider.set_genration_model("command-r")
    provider.client = FakeCohereClient(events=stream)

    assert list(provider.generate_text_stream("question")) == ["first", "second"]


def test_cohere_empty_stream_yields_no_tokens():
    provider = CoHereProvider(api_key="test-key")
    provider.set_genration_model("command-r")
    provider.client = FakeCohereClient(events=[])

    assert list(provider.generate_text_stream("question")) == []


def test_cohere_streaming_failures_are_typed():
    failure = RuntimeError("stream failed")
    provider = CoHereProvider(api_key="test-key")
    provider.set_genration_model("command-r")
    provider.client = FakeCohereClient(error=failure)

    with pytest.raises(LLMStreamingError, match="Cohere token streaming failed") as raised:
        list(provider.generate_text_stream("question"))

    assert raised.value.__cause__ is failure


def test_cohere_stream_iteration_failures_are_typed():
    failure = RuntimeError("iteration failed")
    provider = CoHereProvider(api_key="test-key")
    provider.set_genration_model("command-r")
    provider.client = FakeCohereClient(events=FakeIterable(error=failure))

    with pytest.raises(LLMStreamingError, match="Cohere token streaming failed") as raised:
        list(provider.generate_text_stream("question"))

    assert raised.value.__cause__ is failure


def test_cohere_missing_chat_stream_is_explicitly_unsupported():
    provider = CoHereProvider(api_key="test-key")
    provider.set_genration_model("command-r")
    provider.client = SimpleNamespace()

    with pytest.raises(
        LLMStreamingUnsupportedError,
        match="Cohere client does not support chat_stream",
    ):
        list(provider.generate_text_stream("question"))


def test_cohere_generate_text_remains_compatible():
    provider = CoHereProvider(api_key="test-key")
    provider.set_genration_model("command-r")
    client = FakeCohereGenerateClient()
    provider.client = client

    answer = provider.generate_text("question", [{"role": "USER", "text": "old"}])

    assert answer == "legacy answer"
    assert client.kwargs["message"] == "question"
    assert client.kwargs["chat_history"] == [{"role": "USER", "text": "old"}]
