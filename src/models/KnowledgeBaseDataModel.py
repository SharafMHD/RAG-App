
from sqlalchemy import func

from .BaseDataModel import BaseDataModel
from .db_schemes import KnowledgeBase
from .enums.DatabaseEnum import DatabaseEnum
from sqlalchemy.dialects.postgresql import UUID , insert
from sqlalchemy import select, delete
from models.db_schemes import Asset, DataChunk
from models.enums.AssetTypeEnum import AssetTypeEnum
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
                total_docs = await session.execute(select(func.count(KnowledgeBase.knowledge_base_id)))
                total_docs = total_docs.scalar_one_or_none() or 0
                total_pages = total_docs // page_size
                if total_docs % page_size > 0:
                    total_pages += 1
                query = select(KnowledgeBase).offset((page - 1) * page_size).limit(page_size)
                result = await session.execute(query)
                knowledge_bases = result.scalars().all()
                return knowledge_bases, total_pages, total_docs

    async def get_all_paged_knowledge_bases_with_stats(self, page:int=1, page_size:int=12) -> tuple[list[dict], int, int]:
        """Retrieve paged knowledge bases with document and chunk counts for admin UI."""
        async with self.db_client() as session:
            total_result = await session.execute(select(func.count(KnowledgeBase.knowledge_base_id)))
            total_docs = total_result.scalar_one_or_none() or 0
            total_pages = total_docs // page_size
            if total_docs % page_size > 0:
                total_pages += 1

            document_counts = (
                select(
                    Asset.asset_knowledge_base_id.label("knowledge_base_id"),
                    func.count(Asset.asset_id).label("documents_count"),
                )
                .where(Asset.asset_type == AssetTypeEnum.File.value)
                .group_by(Asset.asset_knowledge_base_id)
                .subquery()
            )
            chunk_counts = (
                select(
                    DataChunk.chunk_knowledge_base_id.label("knowledge_base_id"),
                    func.count(DataChunk.chunk_id).label("chunks_count"),
                )
                .group_by(DataChunk.chunk_knowledge_base_id)
                .subquery()
            )
            query = (
                select(
                    KnowledgeBase,
                    func.coalesce(document_counts.c.documents_count, 0).label("documents_count"),
                    func.coalesce(chunk_counts.c.chunks_count, 0).label("chunks_count"),
                )
                .outerjoin(document_counts, document_counts.c.knowledge_base_id == KnowledgeBase.knowledge_base_id)
                .outerjoin(chunk_counts, chunk_counts.c.knowledge_base_id == KnowledgeBase.knowledge_base_id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(query)
            records = []
            for knowledge_base, documents_count, chunks_count in result.all():
                documents_count = int(documents_count or 0)
                chunks_count = int(chunks_count or 0)
                status = "ready" if chunks_count > 0 else "needs_processing" if documents_count > 0 else "empty"
                records.append({
                    "knowledge_base": knowledge_base,
                    "documents_count": documents_count,
                    "chunks_count": chunks_count,
                    "status": status,
                })
            return records, total_pages, total_docs

    
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
        """Delete a knowledge_base and all related chunks/assets from the database."""
        async with self.db_client() as session:
            await session.execute(delete(DataChunk).where(DataChunk.chunk_knowledge_base_id == knowledge_base_id))
            await session.execute(delete(Asset).where(Asset.asset_knowledge_base_id == knowledge_base_id))
            result = await session.execute(delete(KnowledgeBase).where(KnowledgeBase.knowledge_base_id == knowledge_base_id))
            await session.commit()
        return result.rowcount > 0