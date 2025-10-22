from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import DistanceMethodEnums
import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models

class QdrantDBProvider(VectorDBInterface):
    def __init__(self, db_path: str, distance_method: str) -> None:
        self.client = None
        self.db_path = db_path
        self.distance_method = None

        if distance_method == DistanceMethodEnums.COSINE.value:
            self.distance_method = models.Distance.COSINE
        elif distance_method == DistanceMethodEnums.EUCLIDEAN.value:
            self.distance_method = models.Distance.EUCLIDEAN
        elif distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = models.Distance.DOT
        else:
            logging.error(f"Unsupported distance method: {distance_method}")
            raise ValueError(f"Unsupported distance method: {distance_method}")

        self.logger = logging.getLogger(__name__)

    def connect(self) -> bool:
        try:
            self.client = QdrantClient(path=self.db_path)
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to QdrantDB: {e}")
            return False

    def disconnect(self):
        self.client = None
        raise NotImplementedError("Disconnect method is not required for QdrantDB local instance.")

    def is_collection_exists(self, collection_name: str) -> bool:
        return self.client.collection_exists(collection_name)

    def get_collection_info(self, collection_name: str):
        return self.client.get_collection(collection_name)

    def drop_collection(self, collection_name: str):
        if self.is_collection_exists(collection_name):
            self.client.delete_collection(collection_name)
            self.logger.info(f"Dropped collection: {collection_name}")
        else:
            self.logger.info(f"Collection {collection_name} does not exist.")

    def create_collection(self, collection_name: str, embedding_size: int, do_reset: bool = False):
        # Check if collection exists and matches embedding size
        if self.is_collection_exists(collection_name):
            info = self.get_collection_info(collection_name)
            existing_size = info.config.params.vectors.size
            if existing_size != embedding_size:
                self.logger.warning(f"Vector dimension mismatch: collection expects {existing_size}, got {embedding_size}. Dropping and recreating collection.")
                self.drop_collection(collection_name)
                do_reset = True  # force reset after drop
            else:
                if do_reset:
                    self.drop_collection(collection_name)
                    do_reset = True  # force reset after drop
                else:
                    self.logger.info(f"Collection {collection_name} already exists with correct size {embedding_size}. Skipping creation.")
                    return False

        if not self.is_collection_exists(collection_name) or do_reset:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method
                )
            )

            self.client.update_collection(
                collection_name=collection_name,
                optimizer_config=models.OptimizersConfigDiff(
                    indexing_threshold=1
                )
            )

            self.logger.info(f"Created collection '{collection_name}' with vector size {embedding_size}")
            return True

        return False

    def insert_one_vector(self, collection_name: str, text: str, vector: list, record_id: int = None, metadata: dict = None):
        if not self.is_collection_exists(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return False

        if record_id is None:
            self.logger.error("Record ID must be provided for insert_one_vector")
            return False

        try:
            record = models.Record(
                id=record_id,
                vector=vector,
                payload={
                    "text": text,
                    "metadata": metadata
                }
            )
            self.client.upload_records(
                collection_name=collection_name,
                records=[record]
            )
            self.logger.info(f"Inserted vector with id {record_id} into collection {collection_name}")
            return True

        except Exception as e:
            self.logger.error(f"Error inserting vector: {e}")
            return False

    def insert_many_vectors(self, collection_name: str, texts: list, vectors: list, metadata: list = None, record_ids: list = None, batch_size: int = 100):
        if not self.is_collection_exists(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return False

        if metadata is None:
            metadata = [None] * len(texts)

        if record_ids is None:
            record_ids = list(range(len(texts)))

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_vectors = vectors[i:i + batch_size]
            batch_metadata = metadata[i:i + batch_size]
            batch_record_ids = record_ids[i:i + batch_size]

            batch_records = []
            for idx in range(len(batch_texts)):
                batch_records.append(
                    models.Record(
                        id=batch_record_ids[idx],
                        vector=batch_vectors[idx],
                        payload={
                            "text": batch_texts[idx],
                            "metadata": batch_metadata[idx]
                        }
                    )
                )

            try:
                self.client.upload_records(
                    collection_name=collection_name,
                    records=batch_records
                )
                self.logger.info(f"Inserted batch of {len(batch_records)} vectors into collection {collection_name}")

            except Exception as e:
                self.logger.error(f"Error inserting batch starting at index {i}: {e}")
                return False

        return True

    def search_by_vector(self, collection_name: str, query_vector: list, limit: int = 5):
        print(collection_name)
        if not self.is_collection_exists(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist.")
            return []

        info = self.get_collection_info(collection_name)
        vector_size = info.config.params.vectors.size
        if len(query_vector) != vector_size:
            self.logger.error(f"Query vector size {len(query_vector)} does not match collection vector size {vector_size}")
            return []

        try:
            search_results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit
            )
            self.logger.info(f"Found {len(search_results)} results in collection {collection_name}")
            return search_results

        except Exception as e:
            self.logger.error(f"Error searching vectors: {e}")
            return []
    def list_collections(self) -> list:
        try:
            collections = self.client.get_collections()
            return collections.collections  # If it's an object with .collections attribute
        except Exception as e:
            self.logger.error(f"Error listing collections: {e}")
            return []

