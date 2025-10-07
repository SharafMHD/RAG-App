from pydantic import BaseModel, Field, validator
from typing import Optional
from bson.objectid  import ObjectId
from datetime import datetime, timezone

class Project(BaseModel):
    _id: Optional[ObjectId] 
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