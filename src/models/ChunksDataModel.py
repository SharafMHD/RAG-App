
from .BaseDataModel import BaseDataModel
from .db_schemes import DataChunk
from .enums.DatabaseEnum import DatabaseEnum
from bson.objectid import ObjectId as objectId

class ProjectDataModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client)
        self.db = self.db_client[self.app_settings.MONGODB_DB_NAME]
        self.collection = self.db[DatabaseEnum.COLLECTION_DATA_CHUNKS_NAME.value]

    """Insert a new data chunk into the database."""
    async def insert_data_chunk(self, data_chunk: DataChunk) -> str:
        """Insert a new data chunk into the database."""
        result = await self.collection.insert_one(data_chunk.dict())
        data_chunk._id = result.inserted_id
        return data_chunk
    """Get data chunks by their ID."""
    async def get_data_chunks_by_id(self, chunk_id: str) -> list[DataChunk]:
        result = await self.collection.find_one({"_id": objectId(chunk_id)})
        if result:
            return DataChunk(**result)
        return None