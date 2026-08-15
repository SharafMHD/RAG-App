from types import SimpleNamespace

from stores.llm.Providers.OpenAIProvider import OpenAIProvider


class FakeCompletions:
    def __init__(self, finish_reason="stop", content="ok [source_1]"):
        self.kwargs = {}
        self.kwargs_history = []
        self.responses = [(finish_reason, content)]

    def create(self, **kwargs):
        self.kwargs = kwargs
        self.kwargs_history.append(kwargs)
        finish_reason, content = self.responses.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)])


class FakeClient:
    def __init__(self, completions: FakeCompletions):
        self.chat = SimpleNamespace(completions=completions)


def test_openai_generation_uses_completion_token_limit_parameter():
    provider = OpenAIProvider(api_key="test-key")
    provider.set_genration_model("gpt-5.5")
    completions = FakeCompletions()
    provider.client = FakeClient(completions)

    answer = provider.generate_text("Answer with a citation.", [], max_output_tokens=25)

    assert answer == "ok [source_1]"
    assert completions.kwargs["max_completion_tokens"] == 25
    assert "max_tokens" not in completions.kwargs


def test_openai_generation_omits_temperature_for_gpt_5_models():
    provider = OpenAIProvider(api_key="test-key", default_generation_temperature=0.1)
    provider.set_genration_model("gpt-5.5")
    completions = FakeCompletions()
    provider.client = FakeClient(completions)

    answer = provider.generate_text("Answer with a citation.", [])

    assert answer == "ok [source_1]"
    assert "temperature" not in completions.kwargs


def test_openai_generation_includes_temperature_for_non_gpt_5_models():
    provider = OpenAIProvider(api_key="test-key", default_generation_temperature=0.35)
    provider.set_genration_model("gpt-4o")
    completions = FakeCompletions()
    provider.client = FakeClient(completions)

    answer = provider.generate_text("Answer with a citation.", [])

    assert answer == "ok [source_1]"
    assert completions.kwargs["temperature"] == 0.35


def test_openai_generation_rejects_length_truncated_completion():
    provider = OpenAIProvider(api_key="test-key")
    provider.set_genration_model("gpt-4o")
    completions = FakeCompletions(finish_reason="length")
    provider.client = FakeClient(completions)

    answer = provider.generate_text("Answer with a citation.", [])

    assert answer is None
    assert provider.last_generation_finish_reason == "length"


def test_openai_generation_retries_once_after_length_finish_reason():
    provider = OpenAIProvider(api_key="test-key")
    provider.set_genration_model("gpt-4o")
    completions = FakeCompletions()
    completions.responses = [("length", "partial"), ("stop", "complete [source_1]")]
    provider.client = FakeClient(completions)

    answer = provider.generate_text("Answer with a citation.", [], max_output_tokens=25)

    assert answer == "complete [source_1]"
    assert [call["max_completion_tokens"] for call in completions.kwargs_history] == [25, 50]
    assert provider.last_generation_finish_reason == "stop"
