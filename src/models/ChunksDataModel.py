

from pymongo import InsertOne
from .BaseDataModel import BaseDataModel
from .db_schemes import DataChunk
from .enums.DatabaseEnum import DatabaseEnum
from bson.objectid import ObjectId as objectId
from sqlalchemy import func, select ,delete
from sqlalchemy.dialects.postgresql import UUID


class ChunkDataModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client)
        self.db_client = db_client


    @classmethod
    async def create_instance(cls, db_client: object):
        """Factory method to create an instance of ChunkDataModel and initialize the collection."""
        instance = cls(db_client)
        return instance 
    
    """Insert a new data chunk into the database."""
    async def insert_data_chunk(self, data_chunk: DataChunk) -> str:
        """Insert a new data chunk into the database."""
        async with self.db_client() as session:
            async with session.begin():
                session.add(data_chunk)
            await session.commit()
            await session.refresh(data_chunk)
        return data_chunk
    
    """Bulk insert multiple data chunks into the database."""
    async def bulk_insert_data_chunks(self, data_chunks: list[DataChunk], batch_size:int=100) -> list[str]:
        """Bulk insert multiple data chunks into the database."""
        async with self.db_client() as session:
            async with session.begin():
                for i in range(0, len(data_chunks), batch_size):
                    batch = data_chunks[i:i + batch_size]
                    session.add_all(batch)  
            await session.commit()
            return len(data_chunks)
       

    """Get data chunks by their ID."""
    async def get_data_chunks_by_id(self, chunk_id: UUID) -> list[DataChunk]:
        async with self.db_client() as session:
            await session.execute(select(DataChunk).where(DataChunk.chunk_id == chunk_id))
            data_chunk = session.scalar_one_or_none()
            if data_chunk:
                return data_chunk
            return None
    
    """Delete Chunks by  project"""
    async def delete_chunks_by_project(self, project_id:UUID):
        async with self.db_client() as session: 
            query= delete(DataChunk).where(DataChunk.chunk_project_id == project_id)
            result= await session.execute(query)
            await session.commit()
        return result.rowcount > 0
    
    """Get data chunks by project ID."""
    async def get_data_chunks_by_project(self, project_id: UUID , page_no:int=1 ,page_size:int=50) -> list[DataChunk]:
        async with self.db_client() as session:
            stmt= select(DataChunk).where(DataChunk.chunk_project_id == project_id).offset((page_no - 1) * page_size).limit(page_size)
            result = await session.execute(stmt)
            data_chunks = result.scalars().all()
        return data_chunks
    
    """ Count data chunks by project ID."""
    async def get_total_chunks_count_by_project(self, project_id: UUID) -> int:
        async with self.db_client() as session:
            stmt = select(func.count(DataChunk.chunk_id)).where(DataChunk.chunk_project_id == project_id)
            result = await session.execute(stmt)
            return result.scalar() or 0
