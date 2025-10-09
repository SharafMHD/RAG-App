
from .BaseDataModel import BaseDataModel
from .db_schemes import Assest
from .enums.DatabaseEnum import DatabaseEnum
from bson import ObjectId as objectId
class AssetModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client)
        self.db = self.db_client[self.app_settings.MONGODB_DB_NAME]
        self.collection = self.db[DatabaseEnum.COLLECTION_ASSET_NAME.value]

    @classmethod
    async def create_instance(cls, db_client: object):
        """Factory method to create an instance of ASSETMODEL and initialize the collection."""
        instance = cls(db_client)
        await instance.initialize_collection()
        return instance 
    
    async def initialize_collection(self):
        """Validate if ASSET collection exists, if not create it."""
        existing_collections = await self.db.list_collection_names()
        if DatabaseEnum.COLLECTION_ASSET_NAME.value not in existing_collections:
            await self.db.create_collection(DatabaseEnum.COLLECTION_ASSET_NAME.value)    

        """Initialize the projects collection with necessary indexes."""
        indexes = Assest.get_indexes()
        for index in indexes:
            await self.collection.create_index(
                index["key"], 
                name=index["name"], 
                unique=index["unique"])

    async def create_asset(self, asset: Assest) -> Assest:
        """Create a new Asset in the database."""
        result = await self.collection.insert_one(asset.dict(by_alias=True,exclude_unset=True))
        asset.id = result.inserted_id
        return asset
    
    async def get_all_assets_by_project(self, asset_project_id: str , asset_type:str) -> list[Assest]:
        """Retrieve all assets by its project_id."""
        return await self.collection.find(
            {"asset_project_id": objectId(asset_project_id) if isinstance(asset_project_id , str) else asset_project_id ,
             "asset_type": asset_type}
            ).to_list(length=None)
    

        """Delete a project from the database."""
        result = await self.collection.delete_one({"project_id": project_id})
        return result.deleted_count > 0