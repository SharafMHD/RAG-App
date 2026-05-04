
from sqlalchemy import func

from .BaseDataModel import BaseDataModel
from .db_schemes import Project
from .enums.DatabaseEnum import DatabaseEnum
from sqlalchemy.dialects.postgresql import UUID , insert
from sqlalchemy import select, delete
class ProjectDataModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client)
        self.db_client = db_client

    @classmethod
    async def create_instance(cls, db_client: object):
        """Factory method to create an instance of ProjectDataModel and initialize the collection."""
        instance = cls(db_client)
        return instance 
    

    async def create_project(self, project_data: Project) -> Project:
        """Create a new project or update it if the name already exists."""
        async with self.db_client() as session:
            # 1. Create a dictionary of the data, filtering out the empty project_id
            # We use vars() or project_data.__dict__ to get the attributes
            data_to_insert = {
                "project_name": project_data.project_name,
                "description": project_data.description,
                "owner": project_data.owner,
            }

            # Only add project_id if it's actually set
            if project_data.project_id:
                data_to_insert["project_id"] = project_data.project_id

            stmt = insert(Project).values(**data_to_insert)

            # 2. Define the Upsert logic
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["project_name"], 
                set_={
                    "description": stmt.excluded.description,
                    "owner": stmt.excluded.owner
                }
            ).returning(Project)

            # 3. Execute
            result = await session.execute(upsert_stmt)
            await session.commit()
            
            return result.scalar_one()


    async def get_project_or_create(self, project_id: UUID) -> Project:
        """Retrieve a project by its project_id or create it if it doesn't exist."""
        async with self.db_client() as session:
            # 1. Execute the query through the session
            result = await session.execute(
                select(Project).where(Project.project_id == project_id)
            )
            
            # 2. Now you can call scalar_one_or_none() on the result
            project_data = result.scalar_one_or_none()

            if project_data is None:
                new_project = Project(project_id=project_id)
                # 3. Use await here since create_project is likely async
                return await self.create_project(new_project)
                
            return project_data

       

    async def get_project(self, project_id: UUID) -> Project | None:
        """Retrieve a project by its project_id."""
        async with self.db_client() as session:
            async with session.begin():
                query = select(Project).where(Project.project_id == project_id)
                project_data = query.scalar_one_or_none()
                return project_data
     
    async def get_all_paged_projects(self, page:int=1, page_size:int=100) -> list[Project]:
        """Open session and query all projects with pagination."""
        async with self.db_client() as session:
            async with session.begin():
                """calculate total number of projects in the database."""
                total_docs = await session.execute(select(
                    func.count(Project.project_id)
                    ))
                """calculate total number of pages."""
                total_docs = total_docs.scalar_one_or_none()
                """calculate total number of pages."""
                total_pages = total_docs // page_size
                """if there are remaining documents, add an extra page."""
                if total_docs % page_size > 0:
                    total_pages += 1
                """Retrieve all paged projects from the database."""
                query = select(Project).offset((page - 1) * page_size).limit(page_size)
                projects = await session.execute(query).scalars().all()
                return projects, total_pages, total_docs

    
    async def update_project(self, project_id: UUID, update_data: dict) -> bool:
        """Update an existing project's details."""
        async with self.db_client() as session:
            async with session.begin():
                query = select(Project).where(Project.project_id == project_id)
                project_data = query.scalar_one_or_none()
                if project_data is None:
                    return False
                for key, value in update_data.items():
                    setattr(project_data, key, value)
            await session.commit()
            return True
        
    async def delete_project(self, project_id: UUID) -> bool:
        """Delete a project from the database."""
        async with self.db_client() as session:
                query = delete(Project).where(Project.project_id == project_id)
                result = await session.execute(query)
                await session.commit()
        return result.rowcount > 0