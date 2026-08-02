from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from models.db_schemes.rag_app_db.schemes import AnswerFeedback


class AnswerFeedbackSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    trace_id: str = Field(min_length=1, max_length=255)
    knowledge_base_id: UUID
    rating: Literal["thumbs_up", "thumbs_down"]
    comment: str | None = Field(default=None, max_length=2000)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    citations: list[JsonValue]
    source_chunks: list[JsonValue]
    langfuse_status: Literal["disabled", "sent", "failed"] = "disabled"

    @field_validator("citations", "source_chunks")
    @classmethod
    def reject_secret_fields(cls, value: list[JsonValue]) -> list[JsonValue]:
        def contains_secret(item: JsonValue) -> bool:
            if isinstance(item, dict):
                return any(
                    key in {"api_key", "full_prompt"} or contains_secret(nested)
                    for key, nested in item.items()
                )
            if isinstance(item, list):
                return any(contains_secret(nested) for nested in item)
            return False

        if contains_secret(value):
            raise ValueError("feedback snapshots must not contain secret fields")
        return value


class AnswerFeedbackDataModel:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, submission: AnswerFeedbackSubmission) -> AnswerFeedback:
        values = {
            "trace_id": submission.trace_id,
            "knowledge_base_id": submission.knowledge_base_id,
            "rating": submission.rating,
            "comment": submission.comment,
            "question": submission.question,
            "answer": submission.answer,
            "citations": submission.citations,
            "source_chunks": submission.source_chunks,
            "langfuse_status": submission.langfuse_status,
        }
        statement = insert(AnswerFeedback).values(values)
        upsert_statement = statement.on_conflict_do_update(
            index_elements=[AnswerFeedback.trace_id],
            set_={
                "knowledge_base_id": statement.excluded.knowledge_base_id,
                "rating": statement.excluded.rating,
                "comment": statement.excluded.comment,
                "question": statement.excluded.question,
                "answer": statement.excluded.answer,
                "citations": statement.excluded.citations,
                "source_chunks": statement.excluded.source_chunks,
                "langfuse_status": statement.excluded.langfuse_status,
                "updated_at": func.now(),
            },
        ).returning(AnswerFeedback)
        feedback = self._session.execute(upsert_statement).scalar_one()
        self._session.commit()
        return feedback
