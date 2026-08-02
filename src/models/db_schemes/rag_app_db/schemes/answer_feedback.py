import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from .rag_app_db_base import SQLAlchemyBase


class AnswerFeedback(SQLAlchemyBase):
    __tablename__ = "answer_feedback"

    feedback_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    trace_id = Column(String(255), unique=True, nullable=False)
    knowledge_base_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_bases.knowledge_base_id"),
        nullable=False,
    )
    rating = Column(String(16), nullable=False)
    comment = Column(String(2000), nullable=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    citations = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list)
    source_chunks = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list)
    langfuse_status = Column(String(32), nullable=False, default="disabled")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "rating IN ('thumbs_up', 'thumbs_down')",
            name="ck_answer_feedback_rating",
        ),
        Index("answer_feedback_knowledge_base_id_index", "knowledge_base_id"),
    )
