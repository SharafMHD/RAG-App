from pydantic import BaseModel, Field, field_validator
from typing import Optional


class PushRequest(BaseModel):
    do_reset: Optional[bool] = False


class SearchRequest(BaseModel):
    text: str = Field(..., min_length=1)
    limit: Optional[int] = Field(default=5, ge=1, le=50)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value
