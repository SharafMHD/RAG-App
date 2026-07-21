"""add sprint 4 chunk metadata columns

Revision ID: c8d1e2f3a4b5
Revises: b7c9d0e1f2a3
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c8d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "b7c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    columns = _column_names("data_chunks")
    indexes = _index_names("data_chunks")
    with op.batch_alter_table("data_chunks") as batch_op:
        if "chunking_strategy" not in columns:
            batch_op.add_column(sa.Column("chunking_strategy", sa.String(), nullable=True))
        if "embedding_model" not in columns:
            batch_op.add_column(sa.Column("embedding_model", sa.String(), nullable=True))
        if "content_hash" not in columns:
            batch_op.add_column(sa.Column("content_hash", sa.String(), nullable=True))
        if "parent_chunk_id" not in columns:
            batch_op.add_column(sa.Column("parent_chunk_id", postgresql.UUID(as_uuid=True), nullable=True))
        if "chunk_content_hash_index" not in indexes:
            batch_op.create_index("chunk_content_hash_index", ["content_hash"])


def downgrade() -> None:
    columns = _column_names("data_chunks")
    indexes = _index_names("data_chunks")
    with op.batch_alter_table("data_chunks") as batch_op:
        if "chunk_content_hash_index" in indexes:
            batch_op.drop_index("chunk_content_hash_index")
        for column_name in ("parent_chunk_id", "content_hash", "embedding_model", "chunking_strategy"):
            if column_name in columns:
                batch_op.drop_column(column_name)
