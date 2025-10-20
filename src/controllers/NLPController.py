from .BaseController import BaseController
from models.db_schemes import Project , DataChunk
from stores.llm.LLMEnums import DocumentTypeEums
from typing import List
import json
class NLPController(BaseController):
    def __init__(self,vector_db_client, generation_client,embedding_client):
        super().__init__()

        self.vector_db_client = vector_db_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client

    def create_collection_name(self, project_id:str):
        collection_name = f"collection_{project_id}".strip().replace(" ","_").lower()
        return collection_name
    
    def reset_vector_db_collection(self, project:Project):
        collection_name = self.create_collection_name(str(project.id))
        if self.vector_db_client.collection_exists(collection_name):
            self.vector_db_client.delete_collection(collection_name)
        return collection_name
    
    def get_vector_db_collection_info(self, project:Project):
        collection_name = self.create_collection_name(str(project.id))
        collection_info = self.vector_db_client.get_collection_info(collection_name)
        
        return json.loads(
                json.dumps(collection_info , default=lambda o: o.__dict__)
            )
    
    def index_into_vector_db(self, project:Project, data_chunks:List[DataChunk] , do_reset:bool=False , chunk_ids:List[int]=[]):
        
        #Step 1: Get or create collection
        collection_name = self.create_collection_name(str(project.id))

        #step 2: Prepare embeddings

        texts = [ chunk.chunk_text for chunk in data_chunks ]
        metadata = [ chunk.chunk_metadata for chunk in data_chunks ]

        vectors =[
            self.embedding_client.embedd_text(text=text, document_type = DocumentTypeEums.DOCUMENT.value)
            for text in texts
        ]
        
        print(f"Prepared {len(vectors)} vectors for indexing.")  # Debug statement
        #Step 3: create vector db records if not exist
        _ = self.vector_db_client.create_collection(
            collection_name= collection_name,
            embedding_size= self.embedding_client.embedd_size,
            do_reset= do_reset
        )
        #Step 4: Upsert into vector db
        _= self.vector_db_client.insert_many_vectors(
            collection_name= collection_name,
            texts= texts,
            vectors= vectors,
            metadata= metadata, 
            record_ids= chunk_ids
        )

        return True
    
    def search_index(self, project:Project, text: str, limit:int=5):
         #Step 1: Get or create collection
        collection_name = self.create_collection_name(str(project.id))

        #Step 2: Prepare embedding for search text
        query_vector = self.embedding_client.embedd_text(
            text=text, 
            document_type = DocumentTypeEums.QUERY.value
        )

        if not query_vector or len(query_vector) ==0:
            return False
        

        #Step 3: Search in vector db
        search_results = self.vector_db_client.search_by_vector(
            collection_name= collection_name,
            query_vector= query_vector,
            limit= limit
        )

        print(f"Vectors shape: {query_vector.shape}")  # Check the shape of the vectors array
        print(f"Query shape: {search_results.shape}")  
        if not search_results:
            return False
        
        return json.loads(
                json.dumps(search_results , default=lambda o: o.__dict__)
            )


       