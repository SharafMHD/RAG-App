from types import SimpleNamespace

from stores.llm.Providers.OpenAIProvider import OpenAIProvider


class FakeCompletions:
    def __init__(self):
        self.kwargs = {}

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok [source_1]"))])


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
