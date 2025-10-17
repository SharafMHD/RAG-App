from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import   DistanceMethodEnums
import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models

class QdrantDBProvider(VectorDBInterface):
    def __init__(self, db_path:str, distance_method:str) -> None:
        self.client =None
        self.db_path = db_path
        self.distance_method = None
        if distance_method == DistanceMethodEnums.COSINE.value:
            self.distance_method = models.Distance.COSINE
        elif distance_method == DistanceMethodEnums.EUCLIDEAN.value:
            self.distance_method = models.Distance.EUCLIDEAN
        elif distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = models.Distance.DOT
        else:
            logging.error(f"Unsupported distance method: {distance_method}")
            raise ValueError(f"Unsupported distance method: {distance_method}")
        
        self.looger = logging.getLogger(__name__)
    
    def connect(self) -> bool:
        try:
            self.client = QdrantClient(path=self.db_path)
            return True
        except Exception as e:
            self.looger.error(f"Error connecting to QdrantDB: {e}")
            return False
    def disconnect(self):
        self.client = None
        raise NotImplementedError("Disconnect method is not required for QdrantDB local instance.") 
    
    def is_collection_exists(self, collection_name):
        return self.client.collection_exists(collection_name)
    
    def list_collections(self) -> list:
        return self.client.get_collections()
    
    def get_collection_info(self, collection_name: str) -> dict:
        return self.client.get_collection(collection_name)
    
    def drop_collection(self, collection_name: str):
        if self.is_collection_exists(collection_name):
            self.client.delete_collection(collection_name)
        else:
            self.looger.info(f"Collection {collection_name} does not exist.") 
            return None 

    def create_collection(self, collection_name: str, embedding_size: int, do_reset: bool = False):
        if do_reset:
                self.drop_collection(collection_name)

        if not self.is_collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method
                )
            )
            return True
        return False
    
    def insert_one_vector(self, collection_name: str, text: str, vectors: list, record_id: str = None, metadata: list = None):
        
        if not self.is_collection_exists(collection_name):
            self.looger.error(f"Collection {collection_name} does not exist.")
            return False
        
        try:
            _ = self.client.upload_records(
            collection_name=collection_name,
            records=[
                models.Record(
                    vector=vectors,
                    payload={
                        "text": text,
                        "metadata": metadata
                    }
                    )
                ]
            )
        except Exception as e:
            self.looger.error(f"Error inserting vector: {e}")
            return False
        
        return True
    
    def insert_many_vectors(self, collection_name: str, texts: list, vectors: list, metadata: list = None, record_ids: list = None, batch_size: int = 100):

        if metadata is None:
            metadata = [None] * len(texts)

        if record_ids is None:
            record_ids = [None] * len(texts)

        for i in range(0, len(texts), batch_size):

            batch_end = i + batch_size
            batch_texts = texts[i:batch_end]
            batch_vectors = vectors[i:batch_end]
            batch_metadata = metadata[i:batch_end]

            batch_record = [
                models.Record(
                    vector=batch_vectors[x],
                    payload={
                        "text": batch_texts[x],
                        "metadata": batch_metadata[x]
                    }
                )
                for x in range(len(batch_texts))
            ]

            try:
                _ = self.client.upload_records(
                collection_name=collection_name,
                records=batch_record
            )
            except Exception as e:
                self.looger.error(f"Error inserting batch starting at index {i}: {e}")
                return False
            
        return True
    
    def search_by_vector(self, collection_name: str, query_vector: list, limit: int =5):

        return self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit
        )