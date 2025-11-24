from .BaseController import BaseController
from models.db_schemes import Project , DataChunk
from stores.llm.LLMEnums import DocumentTypeEums
from typing import List
import json
class NLPController(BaseController):
    def __init__(self,vector_db_client, generation_client,embedding_client, template_parser):
        super().__init__()

        self.vector_db_client = vector_db_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser

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
        #Step 3: create vector db records if not exist
        collection_info = self.vector_db_client.create_collection(
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

        if not search_results:
            return False
        
        return search_results
    
    def answer_rag_query(self, project:Project, query_text:str, limit:int=10):
        
        answer, full_prompt, chat_history = None, None, None
        #Step 1: Search index for relevant documents
        retrieved_documents  = self.search_index(
            project= project,
            text= query_text,
            limit= limit
        )
        
        if not retrieved_documents or len(retrieved_documents) == 0:
            return answer, full_prompt, chat_history
        
        # step2: Construct LLM prompt
        system_prompt=self.template_parser.get_template_module("rag", "system_prompt")
        
        documents_prompts = "\n".join([
            self.template_parser.get_template_module("rag", "document_prompt", {
                    "doc_num": idx + 1,
                    "chunk_text": doc.text,
            })
            for idx, doc in enumerate(retrieved_documents)
        ])
        

        footer_prompt=self.template_parser.get_template_module("rag", "footer_prompt", {
            "query_text": query_text,
        })
         # step3: Construct Generation Client Prompts
        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        full_prompt = "\n\n".join([ documents_prompts, query_text,  footer_prompt])
        
       # step4: Retrieve the Answer
        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )
        
        return answer, full_prompt, chat_history

       