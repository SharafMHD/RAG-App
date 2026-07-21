from pydantic import BaseModel, Field, field_validator
from typing import Optional


class ProcessRequest(BaseModel):
    file_id: str | None = None
    chunk_size: Optional[int] = Field(default=900, ge=1)
    overlap_size: Optional[int] = Field(default=150, ge=0)
    do_reset: Optional[bool] = False


class KnowledgeBaseData(BaseModel):
    knowledge_base_name: str = Field(..., min_length=1)
    description: Optional[str] = None
    owner: Optional[str] = "system"

    @field_validator("knowledge_base_name")
    @classmethod
    def knowledge_base_name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("knowledge_base_name must not be blank")
        return value
