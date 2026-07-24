

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
    async def get_data_chunks_by_id(self, chunk_id: UUID) -> DataChunk | None:
        async with self.db_client() as session:
            result = await session.execute(
                select(DataChunk).where(DataChunk.chunk_id == chunk_id)
            )
            return result.scalar_one_or_none()
    
    """Delete Chunks by  knowledge_base"""
    async def delete_chunks_by_knowledge_base(self, knowledge_base_id:UUID):
        async with self.db_client() as session: 
            query= delete(DataChunk).where(DataChunk.chunk_knowledge_base_id == knowledge_base_id)
            result= await session.execute(query)
            await session.commit()
        return result.rowcount > 0
    
    """Get data chunks by knowledge_base ID."""
    async def get_data_chunks_by_knowledge_base(self, knowledge_base_id: UUID , page_no:int=1 ,page_size:int=50) -> list[DataChunk]:
        async with self.db_client() as session:
            stmt= select(DataChunk).where(DataChunk.chunk_knowledge_base_id == knowledge_base_id).offset((page_no - 1) * page_size).limit(page_size)
            result = await session.execute(stmt)
            data_chunks = result.scalars().all()
        return data_chunks
    
    """ Count data chunks by knowledge_base ID."""
    async def get_total_chunks_count_by_knowledge_base(self, knowledge_base_id: UUID) -> int:
        async with self.db_client() as session:
            stmt = select(func.count(DataChunk.chunk_id)).where(DataChunk.chunk_knowledge_base_id == knowledge_base_id)
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def delete_chunks_by_asset(self, asset_id: UUID) -> bool:
        async with self.db_client() as session:
            result = await session.execute(delete(DataChunk).where(DataChunk.chunk_asset_id == asset_id))
            await session.commit()
        return result.rowcount > 0

    async def get_all_data_chunks_by_knowledge_base(self, knowledge_base_id: UUID) -> list[DataChunk]:
        async with self.db_client() as session:
            result = await session.execute(
                select(DataChunk).where(DataChunk.chunk_knowledge_base_id == knowledge_base_id).order_by(DataChunk.chunk_order.asc())
            )
            return result.scalars().all()

    async def get_paged_chunks_by_asset(self, asset_id: UUID, page: int = 1, page_size: int = 20) -> tuple[list[DataChunk], int, int]:
        async with self.db_client() as session:
            total_result = await session.execute(
                select(func.count(DataChunk.chunk_id)).where(DataChunk.chunk_asset_id == asset_id)
            )
            total_count = total_result.scalar_one_or_none() or 0
            total_pages = total_count // page_size
            if total_count % page_size > 0:
                total_pages += 1
            stmt = (
                select(DataChunk)
                .where(DataChunk.chunk_asset_id == asset_id)
                .order_by(DataChunk.chunk_order.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return result.scalars().all(), total_pages, total_count
