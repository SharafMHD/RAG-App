from ..LLMInterface import LLMInterface
from openai import OpenAI
from ..LLMEnums import LLMEnums , OPENAIEnums
from ...LLMInterface import LLMInterface
from openai import OpenAI
from ...LLMEnums import LLMEnums , OPENAIEnums
import logging

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

        self.embedding_model = None
        self.embedd_size= None

        self.client = OpenAI(
            api_key= self.api_key,
            base_url= self.base_url
        )
        self.enums= OPENAIEnums
        self.logger = logging.getLogger(__name__)
    
    def set_genration_model(self, model_id: str) :
        self.generation_model = model_id
    
    def set_embedding_model(self,embedding_model_id:str, embedding_model_size=int) :
        self.embedding_model = embedding_model_id
        self.embedd_size = embedding_model_size

    def process_text(self, text:str):
        return text[:self.default_input_max_tokens].strip()
    
    def generate_text(self, prompt: str,chat_history:list=[],  max_output_tokens: int = None, temperature: float=None) :
        
        if not self.client:
            self.logger.error("OpenAI client was not set.")
            return None
        
        if not self.generation_model:
            self.logger.error("Generation model for OpenAI is not set")
            return None
        
        if max_output_tokens == max_output_tokens : self.default_output_max_tokens
        if temperature == temperature : self.default_generation_temperature
        chat_history.append(
            self.construct_prompt(prompt=prompt,role=OPENAIEnums.USER.value)
        )
        print("chat_history",chat_history)
        response = self.client.chat.completions.create(
            model= self.generation_model,
            messages= chat_history,
            max_tokens= max_output_tokens,
            temperature= temperature
        )
        ##print(chat_history)
        if not response or not response.choices or len(response.choices) ==0 or not response.choices[0].message :
            self.logger.error("Error while generation text with OPENAI")
            return None
        
        # Use dot notation instead of subscript for ChatCompletionMessage object
        return response.choices[0].message.content
    
    def embedd_text(self, text: str , document_type:str =None):
        if not self.client:
            self.logger.error("OpenAI client was not set.")
            return None
        
        if not self.embedding_model:
            self.logger.error("Embedding model for OpenAI is not set")
            return None
        
        # print(f"Using embedding model: {self.embedding_model}")
        # print(f"Client type: {type(self.client)}")

        response = self.client.embeddings.create(
            model= self.embedding_model,
            input=  text,
        )

        if not response or not response.data or len(response.data) ==0 or not response.data[0].embedding:
            self.logger.error("Error while embeding OpenAI.")
            return None

        return response.data[0].embedding
    
    def construct_prompt(self, prompt: str ,role:str):
        return {
            "role" : role,
            "content": self.process_text(prompt)
        }