"""add answer feedback

Revision ID: f1a2b3c4d5e6
Revises: c8d1e2f3a4b5
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "c8d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE_OWNERSHIP_COMMENT = "created_by_alembic_revision:f1a2b3c4d5e6"


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _table_comment(table_name: str) -> str | None:
    return sa.inspect(op.get_bind()).get_table_comment(table_name)["text"]


def upgrade() -> None:
    if "answer_feedback" not in _table_names():
        op.create_table(
            "answer_feedback",
            sa.Column(
                "feedback_id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
            ),
            sa.Column("trace_id", sa.String(length=255), nullable=False),
            sa.Column(
                "knowledge_base_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("knowledge_bases.knowledge_base_id"),
                nullable=False,
            ),
            sa.Column("rating", sa.String(length=16), nullable=False),
            sa.Column("comment", sa.String(length=2000), nullable=True),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column(
                "citations",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "source_chunks",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "langfuse_status",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'disabled'"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "rating IN ('thumbs_up', 'thumbs_down')",
                name="ck_answer_feedback_rating",
            ),
            sa.UniqueConstraint("trace_id", name="uq_answer_feedback_trace_id"),
            comment=_TABLE_OWNERSHIP_COMMENT,
        )
        op.create_index(
            "answer_feedback_knowledge_base_id_index",
            "answer_feedback",
            ["knowledge_base_id"],
        )
        return

    if "answer_feedback_knowledge_base_id_index" not in _index_names("answer_feedback"):
        op.create_index(
            "answer_feedback_knowledge_base_id_index",
            "answer_feedback",
            ["knowledge_base_id"],
        )


def downgrade() -> None:
    if "answer_feedback" not in _table_names():
        return

    if "answer_feedback_knowledge_base_id_index" in _index_names("answer_feedback"):
        op.drop_index("answer_feedback_knowledge_base_id_index", table_name="answer_feedback")

    if _table_comment("answer_feedback") != _TABLE_OWNERSHIP_COMMENT:
        return

    op.drop_table("answer_feedback")
