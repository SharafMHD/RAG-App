

from .BaseDataModel import BaseDataModel
from .db_schemes import Asset
from .enums.DatabaseEnum import DatabaseEnum
from bson import ObjectId as objectId
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func, select, delete
from models.db_schemes import DataChunk
class AssetModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client)
        self.db_client = db_client


    @classmethod
    async def create_instance(cls, db_client: object):
        """Factory method to create an instance of ASSETMODEL and initialize the collection."""
        instance = cls(db_client)
        return instance 
    

    async def create_asset(self, asset: Asset) -> Asset:
        """Create a new Asset in the database."""
        async with self.db_client() as session:
            async with session.begin():
                session.add(asset)
            await session.commit()
            await session.refresh(asset)
        return asset
    
    async def get_all_assets_by_knowledge_base(self, asset_knowledge_base_id: UUID, asset_type: str) -> list[Asset]:
        """Retrieve all assets by its knowledge_base_id."""
        async with self.db_client() as session:
            # 1. Define the statement
            stmt = select(Asset).where(
                Asset.asset_knowledge_base_id == asset_knowledge_base_id,
                Asset.asset_type == asset_type
            )
            
            # 2. Execute and extract scalars in one go
            result = await session.execute(stmt)
            assets_files = result.scalars().all()
            
        return assets_files


    async def get_asset_by_name_and_knowledge_baseid(self, asset_name: str , knowledge_base_id: UUID) -> Asset | None:
        """Retrieve an asset by name and knowledge_base ID."""
        async with self.db_client() as session:
            result = await session.execute(select(Asset).where(
                Asset.asset_name == asset_name,
                Asset.asset_knowledge_base_id == knowledge_base_id
            ))
            return result.scalar_one_or_none()

    async def get_asset_by_id(self, asset_id: UUID) -> Asset | None:
        """Retrieve an asset by ID."""
        async with self.db_client() as session:
            result = await session.execute(select(Asset).where(Asset.asset_id == asset_id))
            return result.scalar_one_or_none()

    async def delete_asset_by_id(self, asset_id: UUID) -> bool:
        """Delete one asset by ID."""
        async with self.db_client() as session:
            result = await session.execute(delete(Asset).where(Asset.asset_id == asset_id))
            await session.commit()
        return result.rowcount > 0

    async def get_paged_assets_with_chunk_counts(self, knowledge_base_id: UUID, page: int = 1, page_size: int = 20) -> tuple[list[dict], int, int]:
        """Retrieve paged assets for a knowledge base with related chunk counts."""
        async with self.db_client() as session:
            total_result = await session.execute(
                select(func.count(Asset.asset_id)).where(Asset.asset_knowledge_base_id == knowledge_base_id)
            )
            total_count = total_result.scalar_one_or_none() or 0
            total_pages = total_count // page_size
            if total_count % page_size > 0:
                total_pages += 1

            chunk_counts = (
                select(
                    DataChunk.chunk_asset_id.label("asset_id"),
                    func.count(DataChunk.chunk_id).label("chunks_count"),
                )
                .group_by(DataChunk.chunk_asset_id)
                .subquery()
            )
            query = (
                select(Asset, func.coalesce(chunk_counts.c.chunks_count, 0).label("chunks_count"))
                .outerjoin(chunk_counts, chunk_counts.c.asset_id == Asset.asset_id)
                .where(Asset.asset_knowledge_base_id == knowledge_base_id)
                .order_by(Asset.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(query)
            return [
                {"asset": asset, "chunks_count": int(chunks_count or 0)}
                for asset, chunks_count in result.all()
            ], total_pages, total_count
        
    
