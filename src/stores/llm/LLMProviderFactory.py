from .LLMEnums import LLMEnums
from .Providers import OpenAIProvider, CoHereProvider


class LLMProvideFactory:
    def __init__(self , config:dict):
        self.config = config
    def create(self , provider:str):
        if provider == LLMEnums.OPENAI.value:
            return OpenAIProvider(
                api_key= self.config.OPENAI_API_KEY,
                base_url=self.config.OPENAI_BASE_URL,
                default_input_max_tokens= self.config.DEFAULT_INPUT_MAX_TOKENS,
                default_output_max_tokens= self.config.DEFAULT_OUTPUT_MAX_TOKENS,
                default_generation_temperature=self.config.DEFAULT_GENERATION_TEMPERATURE
            )
        if provider == LLMEnums.COHERE.value:
            return CoHereProvider(
                api_key=self.config.COHERE_API_KEY,
                default_input_max_tokens= self.config.DEFAULT_INPUT_MAX_TOKENS,
                default_output_max_tokens= self.config.DEFAULT_OUTPUT_MAX_TOKENS,
                default_generation_temperature=self.config.DEFAULT_GENERATION_TEMPERATURE

            )

        return None