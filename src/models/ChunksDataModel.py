
from pymongo import InsertOne
from .BaseDataModel import BaseDataModel
from .db_schemes import DataChunk
from .enums.DatabaseEnum import DatabaseEnum
from bson.objectid import ObjectId as objectId

class ChunkDataModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client)
        self.db = self.db_client[self.app_settings.MONGODB_DB_NAME]
        self.collection = self.db[DatabaseEnum.COLLECTION_DATA_CHUNKS_NAME.value]

    """Insert a new data chunk into the database."""
    async def insert_data_chunk(self, data_chunk: DataChunk) -> str:
        """Insert a new data chunk into the database."""
        result = await self.collection.insert_one(data_chunk.dict(by_alias=True, exclude_unset=True))
        data_chunk._id = result.inserted_id
        return data_chunk
    
    """Bulk insert multiple data chunks into the database."""
    async def bulk_insert_data_chunks(self, data_chunks: list[DataChunk], batch_size:int=100) -> list[str]:
        """Bulk insert multiple data chunks into the database."""
        for i in range(0, len(data_chunks), batch_size):
            batch = data_chunks[i:i + batch_size]
            
            oprations = [
                InsertOne(data_chunk.dict(by_alias=True,exclude_unset=True))
                for data_chunk in batch
            ]
            await self.collection.bulk_write(oprations)
            
        return len(data_chunks)

    """Get data chunks by their ID."""
    async def get_data_chunks_by_id(self, chunk_id: str) -> list[DataChunk]:
        result = await self.collection.find_one({"_id": objectId(chunk_id)})
        if result:
            return DataChunk(**result)
        return None
    
        """Delete Chunks by  project"""
    async def delete_chunks_by_project(self, project_id:object):
        result = await self.collection.delete_many({"chunk_project_id": project_id})
        return result.deleted_count > 0 
    