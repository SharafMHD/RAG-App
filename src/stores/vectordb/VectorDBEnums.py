from enum import Enum

class VectorDBEnums(str, Enum):
    QDRANT = "QDRANT"
    PGVECTOR = "PGVECTOR"

class DistanceMethodEnums(str, Enum):
    COSINE = "COSINE"
    EUCLIDEAN = "EUCLIDEAN"
    DOT = "DOT"

class PGVectorTableSchemaEnums(str, Enum):
    ID = "id"
    TEXT = "text"
    VECTOR = "vector"
    CHUNK_ID = "chunk_id"
    METADATA = "metadata"
    _PRFIX = "pgvector_"

class PGVectorDistanceMethodEnums(str, Enum):
    COSINE = "vector_cosine_ops"
    EUCLIDEAN = "vector_l2_ops"
    DOT = "vector_l2_ops"

class PGVectorIndexTypeEnums(str, Enum):
    IVFFLAT = "ivfflat"
    HNSW = "hnsw"
    BRUTEFORCE = "brute_force"