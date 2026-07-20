
from sqlalchemy import func

from .BaseDataModel import BaseDataModel
from .db_schemes import KnowledgeBase
from .enums.DatabaseEnum import DatabaseEnum
from sqlalchemy.dialects.postgresql import UUID , insert
from sqlalchemy import select, delete
class KnowledgeBaseDataModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client)
        self.db_client = db_client

    @classmethod
    async def create_instance(cls, db_client: object):
        """Factory method to create an instance of KnowledgeBaseDataModel and initialize the collection."""
        instance = cls(db_client)
        return instance 
    

    async def create_knowledge_base(self, knowledge_base_data: KnowledgeBase) -> KnowledgeBase:
        """Create a new knowledge_base or update it if the name already exists."""
        async with self.db_client() as session:
            # 1. Create a dictionary of the data, filtering out the empty knowledge_base_id
            # We use vars() or knowledge_base_data.__dict__ to get the attributes
            data_to_insert = {
                "knowledge_base_name": knowledge_base_data.knowledge_base_name,
                "description": knowledge_base_data.description,
                "owner": knowledge_base_data.owner,
            }

            # Only add knowledge_base_id if it's actually set
            if knowledge_base_data.knowledge_base_id:
                data_to_insert["knowledge_base_id"] = knowledge_base_data.knowledge_base_id

            stmt = insert(KnowledgeBase).values(**data_to_insert)

            # 2. Define the Upsert logic
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["knowledge_base_name"], 
                set_={
                    "description": stmt.excluded.description,
                    "owner": stmt.excluded.owner
                }
            ).returning(KnowledgeBase)

            # 3. Execute
            result = await session.execute(upsert_stmt)
            await session.commit()
            
            return result.scalar_one()


    async def get_knowledge_base_or_create(self, knowledge_base_id: UUID) -> KnowledgeBase:
        """Retrieve a knowledge_base by its knowledge_base_id or create a placeholder knowledge_base."""
        async with self.db_client() as session:
            result = await session.execute(
                select(KnowledgeBase).where(KnowledgeBase.knowledge_base_id == knowledge_base_id)
            )
            knowledge_base_data = result.scalar_one_or_none()

        if knowledge_base_data is None:
            new_knowledge_base = KnowledgeBase(
                knowledge_base_id=knowledge_base_id,
                knowledge_base_name=str(knowledge_base_id),
                owner="system",
            )
            return await self.create_knowledge_base(new_knowledge_base)

        return knowledge_base_data

       

    async def get_knowledge_base(self, knowledge_base_id: UUID) -> KnowledgeBase | None:
        """Retrieve a knowledge_base by its knowledge_base_id."""
        async with self.db_client() as session:
            result = await session.execute(
                select(KnowledgeBase).where(KnowledgeBase.knowledge_base_id == knowledge_base_id)
            )
            return result.scalar_one_or_none()
     
    async def get_all_paged_knowledge_bases(self, page:int=1, page_size:int=100) -> list[KnowledgeBase]:
        """Open session and query all knowledge_bases with pagination."""
        async with self.db_client() as session:
            async with session.begin():
                """calculate total number of knowledge_bases in the database."""
                total_docs = await session.execute(select(
                    func.count(KnowledgeBase.knowledge_base_id)
                    ))
                """calculate total number of pages."""
                total_docs = total_docs.scalar_one_or_none()
                """calculate total number of pages."""
                total_pages = total_docs // page_size
                """if there are remaining documents, add an extra page."""
                if total_docs % page_size > 0:
                    total_pages += 1
                """Retrieve all paged knowledge_bases from the database."""
                query = select(KnowledgeBase).offset((page - 1) * page_size).limit(page_size)
                knowledge_bases = await session.execute(query).scalars().all()
                return knowledge_bases, total_pages, total_docs

    
    async def update_knowledge_base(self, knowledge_base_id: UUID, update_data: dict) -> bool:
        """Update an existing knowledge_base's details."""
        async with self.db_client() as session:
            result = await session.execute(
                select(KnowledgeBase).where(KnowledgeBase.knowledge_base_id == knowledge_base_id)
            )
            knowledge_base_data = result.scalar_one_or_none()
            if knowledge_base_data is None:
                return False
            for key, value in update_data.items():
                setattr(knowledge_base_data, key, value)
            await session.commit()
            return True
        
    async def delete_knowledge_base(self, knowledge_base_id: UUID) -> bool:
        """Delete a knowledge_base from the database."""
        async with self.db_client() as session:
                query = delete(KnowledgeBase).where(KnowledgeBase.knowledge_base_id == knowledge_base_id)
                result = await session.execute(query)
                await session.commit()
        return result.rowcount > 0