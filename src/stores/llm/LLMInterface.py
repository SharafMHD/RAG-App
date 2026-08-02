from abc import ABC, abstractmethod
from collections.abc import Iterator


class LLMStreamingError(RuntimeError):
    """Base error for provider token streaming failures."""


class LLMStreamingUnsupportedError(LLMStreamingError):
    """Raised when a provider client has no native streaming capability."""

class LLMInterface(ABC):
    @abstractmethod
    def set_genration_model(self, model_id: str):
        pass

    @abstractmethod
    def set_embedding_model(self,model_id:str , embedding_size=int) :
        pass
    @abstractmethod
    def generate_text(self, prompt: str, chat_history:list=[], max_output_tokens: int = 150, temperature: float=None):
        pass

    @abstractmethod
    def generate_text_stream(
        self,
        prompt: str,
        chat_history: list | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        pass
    @abstractmethod
    def embedd_text(self, text: str , document_type:str = None):
        pass
    @abstractmethod
    def construct_prompt(self, prompt: str ,role:str):
        pass
