from uuid import UUID
from pkg_resources import safe_name

from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import (DistanceMethodEnums,PGVectorTableSchemaEnums, 
                             PGVectorDistanceMethodEnums, PGVectorIndexTypeEnums)
import logging
from qdrant_client.http import models
from models.db_schemes import RetrievedDocuments
from pgvector.sqlalchemy import Vector
from sqlalchemy.sql.compiler import IdentifierPreparer
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text as sql_text , quoted_name ,bindparam
import json

class PGVectorDBProvider(VectorDBInterface):
    def __init__(self, db_client: str, default_vector_size: int=786, 
                        default_distance_method: str=None, index_threadhold: int = 1000):
        self.client = db_client
        self.default_vector_size = default_vector_size
        self.index_threadhold = index_threadhold

        if default_distance_method == DistanceMethodEnums.COSINE.value:
            default_distance_method = PGVectorDistanceMethodEnums.COSINE.value
        elif default_distance_method == DistanceMethodEnums.EUCLIDEAN.value:
            default_distance_method = PGVectorDistanceMethodEnums.EUCLIDEAN.value
        elif default_distance_method == DistanceMethodEnums.DOT.value:
            default_distance_method = PGVectorDistanceMethodEnums.DOT.value

        self.default_distance_method = default_distance_method

        self.PGVector_table_prefix = PGVectorTableSchemaEnums._PRFIX.value
        self.logger = logging.getLogger("uvicorn")

        self.default_index_name= lambda collection_name: f"{collection_name}_vector_idx"


    async def connect(self) -> bool:
        async with self.client() as session:
            async with session.begin():
                await session.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector"))
            await session.commit()
        return True
    
    async def disconnect(self):
        pass

    async def is_collection_exists(self, collection_name: str) -> bool:
        record = None
        async with self.client() as session:
            async with session.begin():
                list_tbl= sql_text("SELECT * FROM pg_tables WHERE tablename = :table_name")
                result = await session.execute(list_tbl, {"table_name": collection_name})
                record = result.scalar_one_or_none()
        return record 
    
    async def list_collections(self) -> list:
        records= []
        async with self.client() as session:
            async with session.begin():
                list_tbl= sql_text("SELECT tablename FROM pg_tables WHERE tablename LIKE :prefix")
                result = await session.execute(list_tbl, {"prefix": f"{self.PGVector_table_prefix}%"})
                records = result.scalars().all()
        return records
    
    async def get_collection_info(self, collection_name: str) -> dict | None:
        async with self.client() as session:
            async with session.begin():
                get_tbl_info = sql_text("""
                    SELECT schemaname, tablename, tableowner, tablespace, hasindexes
                    FROM pg_tables
                    WHERE tablename = :table_name
                """)

                table_info = await session.execute(
                    get_tbl_info,
                    {"table_name": collection_name}
                )

                table_data = table_info.fetchone()
                if not table_data:
                    return None

                preparer = IdentifierPreparer(postgresql.dialect())
                safe_table_name = preparer.quote(collection_name)

                count_sql = sql_text(f'SELECT COUNT(*) FROM {safe_table_name}')
                records_count = await session.execute(count_sql)

                return {
                    "table_info": {
                        "schemaname": table_data.schemaname,
                        "tablename": table_data.tablename,
                        "tableowner": table_data.tableowner,
                        "tablespace": table_data.tablespace,
                        "hasindexes": table_data.hasindexes,
                    },
                    "records_count": records_count.scalar()
                }
    async def drop_collection(self, collection_name: str) -> bool:
        async with self.client() as session:
            async with session.begin():
                # Manually wrap in double quotes to handle hyphens
                # This turns the name into "collection_1536_..."
                query = f'DROP TABLE IF EXISTS "{collection_name}"'
                
                self.logger.info(f"Dropping collection {collection_name} if it exists.")
                await session.execute(sql_text(query))
                
        self.logger.info(f"Dropped collection {collection_name}.")
        return True
    
    async def create_collection(self, collection_name: str, embedding_size: int, do_reset: bool = False) -> bool:
        if do_reset:
            await self.drop_collection(collection_name)
            self.logger.info(f"Reset collection {collection_name} as do_reset is True.")

        is_collection_exists = await self.is_collection_exists(collection_name)
        if not is_collection_exists:
            self.logger.info(f"Creating collection {collection_name} with embedding size {embedding_size}.")
            
            # 1. Wrap collection_name in double quotes for hyphen safety
            # 2. Use a single f-string for the whole query
            # 3. Use double curly braces {{}} for the literal Postgres JSON empty object
            query = f"""
                CREATE TABLE "{collection_name}" (
                    {PGVectorTableSchemaEnums.ID.value} uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    {PGVectorTableSchemaEnums.TEXT.value} TEXT,
                    {PGVectorTableSchemaEnums.VECTOR.value} VECTOR({embedding_size}),
                    {PGVectorTableSchemaEnums.CHUNK_ID.value} uuid,
                    {PGVectorTableSchemaEnums.METADATA.value} JSONB DEFAULT '{{}}',
                    FOREIGN KEY ({PGVectorTableSchemaEnums.CHUNK_ID.value}) REFERENCES data_chunks(chunk_id) ON DELETE CASCADE
                )
            """
            
            async with self.client() as session:
                async with session.begin():
                    await session.execute(sql_text(query))
                    # await session.commit() <-- Removed (session.begin() handles this)
            return True
        return False

    
    #================PG Vector Indexing Related Methods==================
    # This method checks if the index exists for the given collection and creates it if it does not exist.
    async def is_index_exists(self, collection_name: str) -> bool:
        record = None
        async with self.client() as session:
            async with session.begin():
                list_idx= sql_text("SELECT indexname FROM pg_indexes WHERE tablename = :table_name AND indexname = :index_name")
                result = await session.execute(list_idx, {"table_name": collection_name, "index_name": self.default_index_name(collection_name)})
                record = bool(result.scalar_one_or_none())
        return record
    # This method creates an index for the given collection if it does not exist and if the number of records in the collection is greater than the defined threadhold in config. It returns True if the index is created successfully, False otherwise.
    async def create_index(self, collection_name: str, index_type: str = PGVectorIndexTypeEnums.HNSW.value) -> bool:
        print(f"Checking if index exists for collection {collection_name}...")
        #check if index exists
        if await self.is_index_exists(collection_name):
            self.logger.info(f"Index already exists for collection {collection_name}.")
            return False
        # create index
        async with self.client() as session:
            async with session.begin():
                count_sql = sql_text(f"SELECT COUNT(*) FROM {collection_name}")
                records_count = await session.execute(count_sql)
                records_count = records_count.scalar()
                # check if we have enough records to create index based on the threadhold defined in config
                if records_count < self.index_threadhold:
                    self.logger.info(f" don't have enough records to create index for collection {collection_name}, current count is {records_count}, threadhold is {self.index_threadhold}.")
                    return False
                
                # create index
                self.logger.info(f"START creating index for collection {collection_name}, as current count of records is {records_count}.")
                create_idx_sql = sql_text(
                    f"CREATE INDEX {self.default_index_name(collection_name)} ON {collection_name} "
                    f"USING {index_type} ({PGVectorTableSchemaEnums.VECTOR.value} , {self.default_distance_method} )"
                )
                print(f"create index sql: {create_idx_sql}")
                await session.execute(create_idx_sql)
                await session.commit()
                self.logger.info(f"END creating index for collection {collection_name}.")
    # This method drops the existing index for the given collection and creates a new one. It returns True if the index is reset successfully, False otherwise.
    async def reset_indexing(self, collection_name: str, index_type: str = PGVectorIndexTypeEnums.HNSW.value) -> bool: 
        # drop index if exists
        async with self.client() as session:
            async with session.begin():
                drop_idx_sql = sql_text(f"DROP INDEX IF EXISTS {self.default_index_name(collection_name)}")
                await session.execute(drop_idx_sql)
                await session.commit()
        self.logger.info(f"Dropped index for collection {collection_name} if it existed.")
        # recreate index
        return await self.create_index(collection_name, index_type=index_type) 
    
    #================PG Vector Indexing Related Methods End==================
    
    async def insert_one_vector(self, collection_name: str, text: str, vector: list, record_id: int = None, metadata: dict = None) -> bool:
            # Check if collection exists
            if not await self.is_collection_exists(collection_name):
                self.logger.error(f"Collection {collection_name} does not exist.")
                return False
            
            # validate record_id is provided as its required for insert_one_vector
            if record_id is None:
                self.logger.error("Chunck ID must be provided for insert_one_vector")
                return False
            
            # start insert transaction
            async with self.client() as session:
                async with session.begin():
                    inser_sql = sql_text(
                        f"INSERT INTO {collection_name} ({PGVectorTableSchemaEnums.TEXT.value}, {PGVectorTableSchemaEnums.VECTOR.value}, {PGVectorTableSchemaEnums.CHUNK_ID.value}, {PGVectorTableSchemaEnums.METADATA.value}) "
                        "VALUES (:text, :vector, :chunk_id, :metadata)"
                    )
                    await session.execute(inser_sql, {"text": text, 
                                                    "vector": "[" + ", ".join([f"'{str(v)}'" for v in vector]) + "]", 
                                                    "chunk_id": record_id, 
                                                    "metadata": json.dumps(metadata) if metadata else '{}'})
                    await session.commit()
            return True
        
        
    async def insert_many_vectors(self, collection_name: str, texts: list, vectors: list, metadata: list = None, record_ids: list = None, batch_size: int = 100) -> bool:
        if not await self.is_collection_exists(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return False

        if record_ids is None:
            self.logger.error("record_ids cannot be None.")
            return False

        if not (len(texts) == len(vectors) == len(record_ids)):
            self.logger.error("Length of texts, vectors and record_ids must be the same.")
            return False

        if metadata is None:
            metadata = [None] * len(texts)

        try:
            query = sql_text(f"""
                INSERT INTO "{collection_name}"
                (
                    {PGVectorTableSchemaEnums.TEXT.value},
                    {PGVectorTableSchemaEnums.VECTOR.value},
                    {PGVectorTableSchemaEnums.CHUNK_ID.value},
                    {PGVectorTableSchemaEnums.METADATA.value}
                )
                VALUES (:text, :vector, :chunk_id, :metadata)
            """)

            async with self.client() as session:
                async with session.begin():
                    for i in range(0, len(texts), batch_size):
                        batch_data = []

                        for j in range(i, min(i + batch_size, len(texts))):
                            vector_str = "[" + ",".join(map(str, vectors[j])) + "]"
                            batch_data.append({
                                "text": texts[j],
                                "vector": vector_str,
                                "chunk_id": record_ids[j],
                                "metadata": json.dumps(metadata[j]) if metadata[j] else "{}"
                            })

                        await session.execute(query, batch_data)

            return True

        except Exception as e:
            self.logger.error(f"Error inserting vectors: {e}")
            return False
   
    async def search_by_vector(self, collection_name: str, query_vector: list, limit: int = 10) -> list:
        # Check if collection exists
        if not await self.is_collection_exists(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return []
        
        # pgvector format: [0.1,0.2,0.3]
        query_vector_str = "[" + ",".join(str(float(v)) for v in query_vector) + "]"

        preparer = IdentifierPreparer(postgresql.dialect())
        safe_collection_name = preparer.quote(collection_name)

        async with self.client() as session:
            async with session.begin():
                search_sql_stmt = sql_text(f"""
                    SELECT
                        {PGVectorTableSchemaEnums.TEXT.value} AS text,
                        1 - ({PGVectorTableSchemaEnums.VECTOR.value} <-> CAST(:query_vector AS vector)) AS score
                    FROM {safe_collection_name}
                    ORDER BY {PGVectorTableSchemaEnums.VECTOR.value} <-> CAST(:query_vector AS vector)
                    LIMIT :limit
                """)

                result = await session.execute(
                    search_sql_stmt,
                    {
                        "query_vector": query_vector_str,
                        "limit": limit
                    }
                )

                records = result.fetchall()

                return [
                    RetrievedDocuments(
                        text=record.text,
                        score=record.score
                    )
                    for record in records
                ]