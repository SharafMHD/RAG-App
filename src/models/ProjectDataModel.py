
from .BaseDataModel import BaseDataModel
from .db_schemes import Project
from .enums.DatabaseEnum import DatabaseEnum

class ProjectDataModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client)
        self.db = self.db_client[self.app_settings.MONGODB_DB_NAME]
        self.collection = self.db[DatabaseEnum.COLLECTION_PROJECTS_NAME.value]

    @classmethod
    async def create_instance(cls, db_client: object):
        """Factory method to create an instance of ProjectDataModel and initialize the collection."""
        instance = cls(db_client)
        await instance.initialize_collection()
        return instance 
    
    async def initialize_collection(self):
        """Validate if project collection exists, if not create it."""
        existing_collections = await self.db.list_collection_names()
        if DatabaseEnum.COLLECTION_PROJECTS_NAME.value not in existing_collections:
            await self.db.create_collection(DatabaseEnum.COLLECTION_PROJECTS_NAME.value)    

        """Initialize the projects collection with necessary indexes."""
        indexes = Project.get_indexes()
        for index in indexes:
            await self.collection.create_index(
                index["key"], 
                name=index["name"], 
                unique=index["unique"])

    async def create_project(self, project_data: Project) -> Project:
        """Create a new project in the database."""
        result = await self.collection.insert_one(project_data.dict(by_alias=True,exclude_unset=True))
        project_data.id = result.inserted_id
        return project_data
    
    async def get_project_or_create(self, project_id: str) -> Project:
        """Retrieve a project by its project_id or create it if it doesn't exist."""
        record = await self.collection.find_one({"project_id": project_id})
        if record is None:
            new_project = Project(project_id=project_id)
            return await self.create_project(new_project)
        return Project(**record)

    async def get_project(self, project_id: str) -> Project | None:
        """Retrieve a project by its project_id."""
        project_data = await self.collection.find_one({"project_id": project_id})
        if project_data:
            return Project(**project_data)
        return None 
     
    async def get_all_paged_projects(self, page:int=1, page_size:int=100) -> list[Project]:
        """calculate total number of projects in the database."""
        total_docs = await self.collection.count_documents({})

        """calculate total number of pages."""
        total_pages = total_docs // page_size
        if total_docs % page_size != 0:
            total_pages += 1

        """Retrieve all paged projects from the database."""
        cursor = self.collection.find().skip((page - 1) * page_size).limit(page_size)
        projects = []
        async for project_data in cursor:
            projects.append(Project(**project_data))
        return projects , total_pages, total_docs
    
    async def update_project(self, project_id: str, update_data: dict) -> bool:
        """Update an existing project's details."""
        result = await self.collection.update_one(
            {"project_id": project_id}, {"$set": update_data}
        )
        return result.modified_count > 0

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project from the database."""
        result = await self.collection.delete_one({"project_id": project_id})
        return result.deleted_count > 0