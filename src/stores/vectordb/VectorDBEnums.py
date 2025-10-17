from enum import Enum

class VectorDBEnums(str, Enum):
    QDRANT = "QDRANT"

class DistanceMethodEnums(str, Enum):
    COSINE = "COSINE"
    EUCLIDEAN = "EUCLIDEAN"
    DOT = "DOT"