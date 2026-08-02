from ..LLMInterface import LLMInterface
from ..LLMInterface import LLMStreamingError, LLMStreamingUnsupportedError
import cohere
from ..LLMEnums import LLMEnums , CohereEums , DocumentTypeEums
import logging
from collections.abc import Iterator

class CoHereProvider(LLMInterface):
        def __init__(self, api_key: str, 
                  default_input_max_tokens: int=1000, 
                  default_output_max_tokens:int=1000,
                  default_generation_temperature:float=0.1):
                
            self.api_key= api_key

            self.default_input_max_tokens = default_input_max_tokens
            self.default_output_max_tokens=default_output_max_tokens
            self.default_generation_temperature=default_generation_temperature

            self.generation_model = None

            self.embedding_model = None
            self.embedd_size= None

            self.client = cohere.client_v2.ClientV2(api_key=self.api_key)
            self.enums = CohereEums

            self.logger = logging.getLogger(__name__)

        def set_genration_model(self, model_id: str) :
            self.generation_model = model_id

        def set_embedding_model(self,model_id:str, embedding_model_size=int) :
            self.embedding_model = model_id
            self.embedd_size = embedding_model_size

        def process_text(self, text:str):
            return text[:self.default_input_max_tokens].strip()
        
        def generate_text(self, prompt: str, chat_history: list | None = None, max_output_tokens: int = 150, temperature: float = None):
            if not self.client:
                self.logger.error("CoHere client was not set.")
                return None

            if not self.generation_model:
                self.logger.error("Generation model for CoHere is not set")
                return None

            max_output_tokens = max_output_tokens or self.default_output_max_tokens
            temperature = self.default_generation_temperature if temperature is None else temperature

            try:
                response = self.client.chat(
                    model=self.generation_model,
                    chat_history=list(chat_history or []),
                    message=self.process_text(prompt),
                    temperature=temperature,
                    max_tokens=max_output_tokens,
                )
            except Exception as exc:
                self.logger.exception("Error while generating text with CoHere: %s", exc)
                return None

            if not response or not response.message.content[0].text:
                self.logger.error("Error while generating text with CoHere")
                return None

            return response.message.content[0].text

        def generate_text_stream(
            self,
            prompt: str,
            chat_history: list | None = None,
            max_output_tokens: int | None = None,
            temperature: float | None = None,
        ) -> Iterator[str]:
            if not self.client:
                raise LLMStreamingError("Cohere client was not set")

            if not self.generation_model:
                raise LLMStreamingError("Cohere generation model was not set")

            chat_stream = getattr(self.client, "chat_stream", None)
            if not callable(chat_stream):
                raise LLMStreamingUnsupportedError(
                    "Cohere client does not support chat_stream"
                )

            max_output_tokens = max_output_tokens or self.default_output_max_tokens
            temperature = self.default_generation_temperature if temperature is None else temperature
            role_map = {
                CohereEums.SYSTEM.value: "system",
                CohereEums.USER.value: "user",
                CohereEums.ASSISTANT.value: "assistant",
            }
            messages = [
                {
                    "role": role_map.get(message["role"], message["role"]),
                    "content": message["text"],
                }
                for message in chat_history or []
            ]
            messages.append({"role": "user", "content": self.process_text(prompt)})

            try:
                stream = chat_stream(
                    model=self.generation_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_output_tokens,
                )
                for event in stream:
                    if getattr(event, "type", None) != "content-delta":
                        continue
                    delta = getattr(event, "delta", None)
                    message = getattr(delta, "message", None)
                    content = getattr(message, "content", None)
                    text = getattr(content, "text", None)
                    if text:
                        yield text
            except Exception as exc:
                raise LLMStreamingError("Cohere token streaming failed") from exc

        def embedd_text(self, text: str , document_type:str = None):
            if not self.client:
                self.logger.error("CoHere client was not set.")
                return None
        
            if not self.embedding_model:
                self.logger.error("Embedding model for CoHere is not set")
                return None
            
            input_type = CohereEums.DOCUMENT.value
            if document_type == DocumentTypeEums.QUERY.value:
                input_type = CohereEums.QUERY.value

            if isinstance(text, str):
                texts = [self.process_text(text)]
            else:
                texts = [self.process_text(item) for item in text]

            try:
                response = self.client.embed(
                    model=self.embedding_model,
                    texts=texts,
                    input_type=input_type,
                    embedding_types=['float'],
                )
            except Exception as exc:
                self.logger.exception("Error while embedding with CoHere: %s", exc)
                return None

            if not response or not response.embeddings or not response.embeddings.float_:
                self.logger.error("Error while embedding with CoHere.")
                return None

            return response.embeddings.float_

        def construct_prompt(self, prompt: str ,role:str):
            return {
                "role" : role,
                "text": self.process_text(prompt)
            }

