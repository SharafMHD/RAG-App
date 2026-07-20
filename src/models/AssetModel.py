

from .BaseDataModel import BaseDataModel
from .db_schemes import Asset
from .enums.DatabaseEnum import DatabaseEnum
from bson import ObjectId as objectId
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import select, delete
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
        
    
