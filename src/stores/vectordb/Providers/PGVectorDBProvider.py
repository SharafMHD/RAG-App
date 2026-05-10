from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import (DistanceMethodEnums,PGVectorTableSchemaEnums, 
                             PGVectorDistanceMethodEnums, PGVectorIndexTypeEnums)
import logging
from qdrant_client.http import models
from models.db_schemes import RetrievedDocuments

from sqlalchemy.sql import text as sql_text
import json

class PGVectorDBProvider(VectorDBInterface):
    def __init__(self, db_client: str, default_vector_size: int=786, 
                        default_distance_method: str=None, index_threadhold: int = 1000):
        self.client = db_client
        self.default_vector_size = default_vector_size
        self.default_distance_method = default_distance_method
        self.index_threadhold = index_threadhold

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
    
    async def get_collection_info(self, collection_name) -> dict:
        
        async with self.client() as session:
            async with session.begin():
                get_tbl_info = sql_text("""
                    SELECT schemaname, tablename,tableowner,tablespace,hasindexes 
                    FROM pg_tables
                    WHERE tablename = :table_name
                """)
                count_sql = sql_text(f"SELECT COUNT(*) FROM {collection_name}")

                table_info = await session.execute(get_tbl_info, {"table_name": collection_name})
                records_count = await session.execute(count_sql)
                
                table_data = table_info.fetchone()
                if not table_data:
                    return None
                return {
                    "table_info": dict(table_data),
                    "records_count": records_count.scalar()
                }
    
    async def drop_collection(self, collection_name: str) -> bool:
            async with self.client() as session:
                async with session.begin():
                    drop_tbl = sql_text(f"DROP TABLE IF EXISTS {collection_name}")
                    self.logger.info(f"Dropping collection {collection_name} if it exists.")
                    await session.execute(drop_tbl)
                    await session.commit()
            self.logger.info(f"Dropped collection {collection_name}.")
            return True
    
    async def create_collection(self, collection_name: str, embedding_size: int, do_reset: bool = False) -> bool:

        # check if do_reset is True, if so drop the collection if exists
        if do_reset:
            _= await self.drop_collection(collection_name)
            self.logger.info(f"Reset collection {collection_name} as do_reset is True.")

        # Check if collection exists 
        is_collection_exists = await self.is_collection_exists(collection_name)
        if not is_collection_exists:
            self.logger.info(f"Creating collection {collection_name} with embedding size {embedding_size}.")
            async with self.client() as session:
                async with session.begin():
                    create_tbl = sql_text(
                        'CREATE TABLE {collection_name} ('
                            f'{PGVectorTableSchemaEnums.ID.value} uuid PRIMARY KEY DEFAULT gen_random_uuid(),'
                            f'{PGVectorTableSchemaEnums.TEXT.value} TEXT,'
                            f'{PGVectorTableSchemaEnums.VECTOR.value} VECTOR({embedding_size}),'
                            f'{PGVectorTableSchemaEnums.CHUNK_ID.value} uuid,'
                            f'{PGVectorTableSchemaEnums.METADATA.value} JSONB DEFAULT \'{{}}\''
                            f'FOREIGN KEY ({PGVectorTableSchemaEnums.CHUNK_ID.value}) REFERENCES data_chunks(chunk_id) ON DELETE CASCADE'
                        ')'
                    )
                    await session.execute(create_tbl)
                    await session.commit()
            return True
        return False
    
    #================PG Vector Indexing Related Methods==================
    # This method checks if the index exists for the given collection and creates it if it does not exist.
    async def is_index_exists(self, collection_name: str) -> bool:
        record = None
        async with self.client.connect() as session:
            async with session.begin():
                list_idx= sql_text("SELECT indexname FROM pg_indexes WHERE tablename = :table_name AND indexname = :index_name")
                result = await session.execute(list_idx, {"table_name": collection_name, "index_name": self.default_index_name(collection_name)})
                record = bool(result.scalar_one_or_none())
        return record
    # This method creates an index for the given collection if it does not exist and if the number of records in the collection is greater than the defined threadhold in config. It returns True if the index is created successfully, False otherwise.
    async def create_index(self, collection_name: str, index_type: str = PGVectorIndexTypeEnums.HNSW.value) -> bool:
        #check if index exists
        if await self.is_index_exists(collection_name):
            self.logger.info(f"Index already exists for collection {collection_name}.")
            return False
        # create index
        async with self.client.connect() as session:
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
                await session.execute(create_idx_sql)
                await session.commit()
                self.logger.info(f"END creating index for collection {collection_name}.")
    # This method drops the existing index for the given collection and creates a new one. It returns True if the index is reset successfully, False otherwise.
    async def reset_indexing(self, collection_name: str, index_type: str = PGVectorIndexTypeEnums.HNSW.value) -> bool: 
        # drop index if exists
        async with self.client.connect() as session:
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
        async with self.client.connect() as session:
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
        # Check if collection exists
        if not await self.is_collection_exists(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return False
        
        # validate length of texts, vectors, record_ids and metadata if provided
        if not (len(texts) == len(vectors) == len(record_ids)):
            self.logger.error("Length of texts, vectors and record_ids must be the same.")
            return False
        
        #validate metadata length if provided
        if not metadata or len(metadata) ==0:
            self.logger.info("Metadata not provided for insert_many_vectors, defaulting to empty metadata for all records.")
            metadata = [None] * len(texts)
        
        # start insert transaction
        try:
            async with self.client.connect() as session:
                async with session.begin():
                    for i in range(0, len(texts), batch_size):
                        batch_texts = texts[i:i + batch_size]
                        batch_vectors = vectors[i:i + batch_size]
                        batch_metadata = metadata[i:i + batch_size] if metadata else [None] * len(batch_texts)
                        batch_record_ids = record_ids[i:i + batch_size]

                        values =[]
                        for _text, _vector, _metadata, _record_id in zip(batch_texts, batch_vectors, batch_metadata, batch_record_ids):
                            values.append(f"('{_text}', '[{', '.join([f'{str(v)}' for v in _vector])}]', '{_record_id}', '{json.dumps(_metadata) if _metadata else '{}'}')")

                        batch_insert_sql = sql_text(
                            f"INSERT INTO {collection_name} ({PGVectorTableSchemaEnums.TEXT.value}, {PGVectorTableSchemaEnums.VECTOR.value}, {PGVectorTableSchemaEnums.CHUNK_ID.value}, {PGVectorTableSchemaEnums.METADATA.value}) "
                            "VALUES " + ", ".join(values)
                        )
                        await session.execute(batch_insert_sql)
                    await session.commit()  
            return True
        except Exception as e:
            self.logger.error(f"Error inserting vectors: {e}")
            return False
    
    async def search_by_vector(self, collection_name: str, query_vector: list, limit: int = 10) -> list:
        # Check if collection exists
        if not await self.is_collection_exists(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return []
        
        # convert vector to string format for SQL query
        query_vector_str = "[" + ", ".join([f"'{str(v)}'" for v in query_vector]) + "]"

        # start search transaction
        async with self.client.connect() as session:
            async with session.begin():
                search_sql_stmt= sql_text(
                    f"SELECT {PGVectorTableSchemaEnums.ID.value} as text, 1- ({PGVectorTableSchemaEnums.VECTOR.value} <-> '{query_vector_str}') as score FROM {collection_name} "
                    f"ORDER BY score DESC "
                    f"LIMIT {limit}"
                )
                result = await session.execute(search_sql_stmt, {"query_vector": query_vector_str})
                records = result.fetchall()
                return [
                    RetrievedDocuments(
                        text=record.text,
                        score=record.score
                    )
                    for record in records
                ]
