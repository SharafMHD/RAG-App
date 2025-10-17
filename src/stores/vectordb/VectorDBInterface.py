from abc import ABC, abstractmethod
from typing import List
class VectorDBInterface(ABC):
    @abstractmethod
    def connect(self, connection_string: str):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def is_collection_exists(self, collection_name: str) -> bool:
        pass    

    @abstractmethod
    def list_collections(self) -> List:
        pass

    @abstractmethod
    def get_collection_info(self, collection_name: str) -> dict:
        pass

    @abstractmethod
    def drop_collection(self, collection_name: str):
        pass

    @abstractmethod
    def create_collection(self, collection_name: str, 
                          embedding_size: int , 
                          do_reset: bool = False):
        pass

    @abstractmethod
    def insert_one_vector(self, collection_name: str,
                           text: str, vectors: list,
                            record_id: str = None, 
                            metadata: list = None):
        pass
    @abstractmethod
    def insert_many_vectors(self, collection_name: str, 
                            texts: list,
                            vectors: list, 
                            metadata: list = None,
                            record_ids: list = None,
                            batch_size: int = 100):
        pass

    @abstractmethod
    def search_by_vector(self, collection_name: str, query_vector: list, limit: int =5):
        pass

