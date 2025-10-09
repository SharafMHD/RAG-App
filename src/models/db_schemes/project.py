from pydantic import BaseModel, Field, validator
from typing import Optional
from bson.objectid  import ObjectId
from datetime import datetime, timezone

class Project(BaseModel):
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    project_id: str = Field(..., min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  

    @validator("project_id")
    def project_id_must_not_be_empty(cls, value):
        if not value.isalnum():
            raise ValueError("project_id must be alphanumeric")
        return value
    class Config:
        arbitrary_types_allowed = True

    """"Get indexes for the collection """
    @classmethod
    def get_indexes(cls):
        return [
                {
                    "key": [("project_id", 1)],
                    "name": "unique_project_id_index_1",
                    "unique": True,
                }
            ]  # Unique index on project_id