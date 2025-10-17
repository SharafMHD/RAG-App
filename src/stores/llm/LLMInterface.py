from abc import ABC, abstractmethod

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
    def embedd_text(self, text: str , document_type:str = None):
        pass
    @abstractmethod
    def constract_prompt(self, prompt: str ,role:str):
        pass