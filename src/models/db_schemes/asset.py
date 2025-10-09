from pydantic import BaseModel, Field, validator
from typing import Optional
from bson.objectid  import ObjectId
from datetime import datetime, timezone


class Assest(BaseModel):
    id: Optional[ObjectId] = Field(default=None, alias="_id")
    asset_project_id: ObjectId
    asset_name: str = Field(..., min_length=1)
    asset_type: str = Field(..., min_length=1)
    asset_szie: int = Field(gt=0, default=None)
    asset_config: dict = Field(default=None)
    created_at: datetime = Field(default= datetime.now(timezone.utc))
    updated_at: datetime = Field(default= datetime.now(timezone.utc))  

    class Config:
        arbitrary_types_allowed = True

    """"Get indexes for the collection """
    @classmethod
    def get_indexes(cls):
        return [
                {
                    "key": [("asset_project_id", 1)],
                    "name": "unique_asset_project_id_index_1",
                    "unique": False,
                },
                 {
                    "key": [
                        ("asset_project_id", 1),
                        ("asset_name", 1)
                        ],
                    "name": "unique_asset_project_id__name_index_1",
                    "unique": True,
                }
            ]  # Unique index on project_id