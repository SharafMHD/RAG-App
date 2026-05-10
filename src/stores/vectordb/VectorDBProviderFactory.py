from .Providers import QdrantDBProvider , PGVectorDBProvider
from .VectorDBEnums import VectorDBEnums
from controllers.BaseController import BaseController
from sqlalchemy.orm import sessionmaker
class VectorDBProviderFactory:
    def __init__(self , config , db_client: sessionmaker= None):
        self.config = config
        self.db_client = db_client
        self.base_controller = BaseController()

    def create(self , provider:str):
        if provider == VectorDBEnums.QDRANT.value:
            return QdrantDBProvider(
                db_client=self.base_controller.get_vector_db_path(self.config.VECTOR_DB_PATH),
                distance_method=self.config.VECTOR_DB_DISTANCE_METHOD,
                default_vector_size=self.config.EMBEDDING_MODEL_SIZE,
                index_threadhold=self.config.PGVECTOR_INDEX_THREADHOLD
            )
        
        if provider == VectorDBEnums.PGVECTOR.value:
            return PGVectorDBProvider(
                db_client=self.db_client,
                default_distance_method=self.config.VECTOR_DB_DISTANCE_METHOD,
                default_vector_size=self.config.EMBEDDING_MODEL_SIZE,
                index_threadhold=self.config.PGVECTOR_INDEX_THREADHOLD
            )
        return None