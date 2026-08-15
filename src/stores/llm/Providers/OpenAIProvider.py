from ..LLMInterface import LLMInterface
from openai import OpenAI
from ..LLMEnums import LLMEnums , OPENAIEnums
from ..LLMInterface import LLMStreamingError
import logging
from collections.abc import Iterator
from typing import List, Union

class OpenAIProvider(LLMInterface):
    def __init__(self, api_key: str, 
                 
        base_url: str = None,
        default_input_max_tokens: int=10000, 
        default_output_max_tokens:int=10000,
        default_generation_temperature:float=0.1):  
     
        self.api_key= api_key
        self.base_url=base_url
        self.default_input_max_tokens = default_input_max_tokens
        self.default_output_max_tokens=default_output_max_tokens
        self.default_generation_temperature=default_generation_temperature

        self.client = OpenAI(api_key=api_key, base_url=base_url)

        self.generation_model = None
        self.last_generation_finish_reason = None

        self.embedding_model = None
        self.embedd_size= None

        self.client = OpenAI(
            api_key= self.api_key,
            base_url= self.base_url
        )
        self.enums= OPENAIEnums
        self.logger = logging.getLogger("uvicorn")
    
    def set_genration_model(self, model_id: str) :
        self.generation_model = model_id
    
    def set_embedding_model(self,embedding_model_id:str, embedding_model_size=int) :
        self.embedding_model = embedding_model_id
        self.embedd_size = embedding_model_size

    def process_text(self, text:str):
        return text[:self.default_input_max_tokens].strip()
    
    def generate_text(self, prompt: str, chat_history: list | None = None, max_output_tokens: int = None, temperature: float = None):
        self.last_generation_finish_reason = None
        if not self.client:
            self.logger.error("OpenAI client was not set.")
            return None

        if not self.generation_model:
            self.logger.error("Generation model for OpenAI is not set")
            return None

        max_output_tokens = max_output_tokens or self.default_output_max_tokens
        temperature = self.default_generation_temperature if temperature is None else temperature
        messages = list(chat_history or [])
        messages.append(
            self.construct_prompt(prompt=prompt, role=OPENAIEnums.USER.value)
        )

        request_options = {
            "model": self.generation_model,
            "messages": messages,
            "max_completion_tokens": max_output_tokens,
        }
        if not self.generation_model.startswith("gpt-5"):
            request_options["temperature"] = temperature

        for output_tokens in (max_output_tokens, max_output_tokens * 2):
            request_options["max_completion_tokens"] = output_tokens
            try:
                response = self.client.chat.completions.create(**request_options)
            except Exception as exc:
                self.logger.exception("Error while generating text with OpenAI: %s", exc)
                return None

            if not response or not response.choices or len(response.choices) == 0 or not response.choices[0].message:
                self.logger.error("Error while generating text with OpenAI")
                return None

            self.last_generation_finish_reason = getattr(response.choices[0], "finish_reason", None)
            if self.last_generation_finish_reason == "length" and output_tokens == max_output_tokens:
                self.logger.warning("Retrying OpenAI generation after length finish_reason")
                continue
            if self.last_generation_finish_reason not in (None, "stop"):
                self.logger.error("OpenAI generation did not finish cleanly: %s", self.last_generation_finish_reason)
                return None

            return response.choices[0].message.content

        return None

    def generate_text_stream(
        self,
        prompt: str,
        chat_history: list | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        self.last_generation_finish_reason = None
        if not self.client:
            raise LLMStreamingError("OpenAI client was not set")

        if not self.generation_model:
            raise LLMStreamingError("OpenAI generation model was not set")

        max_output_tokens = max_output_tokens or self.default_output_max_tokens
        temperature = self.default_generation_temperature if temperature is None else temperature
        messages = list(chat_history or [])
        messages.append(
            self.construct_prompt(prompt=prompt, role=OPENAIEnums.USER.value)
        )

        base_request_options = {
            "model": self.generation_model,
            "messages": messages,
            "max_completion_tokens": max_output_tokens,
            "stream": True,
        }
        if not self.generation_model.startswith("gpt-5"):
            base_request_options["temperature"] = temperature

        for output_tokens in (max_output_tokens, max_output_tokens * 2):
            tokens: list[str] = []
            self.last_generation_finish_reason = None
            request_options = {**base_request_options, "max_completion_tokens": output_tokens}
            try:
                stream = self.client.chat.completions.create(**request_options)
                for chunk in stream:
                    choices = getattr(chunk, "choices", None)
                    if not choices:
                        continue
                    finish_reason = getattr(choices[0], "finish_reason", None)
                    if finish_reason is not None:
                        self.last_generation_finish_reason = finish_reason
                    delta = getattr(choices[0], "delta", None)
                    content = getattr(delta, "content", None)
                    if content:
                        tokens.append(content)
            except Exception as exc:
                raise LLMStreamingError("OpenAI token streaming failed") from exc
            if self.last_generation_finish_reason == "length" and output_tokens == max_output_tokens:
                continue
            if self.last_generation_finish_reason not in (None, "stop"):
                raise LLMStreamingError("OpenAI token streaming was truncated")
            yield from tokens
            return

        raise LLMStreamingError("OpenAI token streaming was truncated")
    
    def embedd_text(self, text: Union[str, List[str]], document_type:str =None):
        if not self.client:
            self.logger.error("OpenAI client was not set.")
            return None
        
        if not self.embedding_model:
            self.logger.error("Embedding model for OpenAI is not set")
            return None
        
        # validate if single string is passed, convert to list
        if isinstance(text, str):
            text = [text]

        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
            )
        except Exception as exc:
            self.logger.exception("Error while embedding with OpenAI: %s", exc)
            return None

        if not response or not response.data or len(response.data) == 0 or not response.data[0].embedding:
            self.logger.error("Error while embedding with OpenAI.")
            return None
        return [item.embedding for item in response.data]
            
    def construct_prompt(self, prompt: str ,role:str):
        return {
            "role" : role,
            "content": prompt
        }
