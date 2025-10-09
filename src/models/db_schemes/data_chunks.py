from pydantic import BaseModel, Field, validator
from typing import Optional
from bson.objectid  import ObjectId
from datetime import datetime, timezone


class DataChunk(BaseModel):
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    chunk_text: str = Field(..., min_length=1)
    chunk_metadata: Optional[dict] = None
    chunk_order: int = Field(..., gt=0)
    chunk_project_id: str = ObjectId
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  

    class Config:
        arbitrary_types_allowed = True

    """"Get indexes for the collection """
    @classmethod
    def get_indexes(cls):
        return [
                {
                    "key": [("chunk_project_id", 1)],
                    "name": "unique_chunk_project_id_index_1",
                    "unique": False,
                }
            ]  # Unique index on project_id