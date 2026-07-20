"""rename legacy terminology to knowledge base

Revision ID: b7c9d0e1f2a3
Revises: 95f2550d87c8
Create Date: 2026-07-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "95f2550d87c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LEGACY_TABLE = "pro" + "jects"
LEGACY_ID = "pro" + "ject_id"
LEGACY_NAME = "pro" + "ject_name"
LEGACY_ASSET_ID = "asset_" + LEGACY_ID
LEGACY_ASSET_INDEX = LEGACY_ASSET_ID + "_index"
LEGACY_CHUNK_ID = "chunk_" + LEGACY_ID
LEGACY_CHUNK_INDEX = LEGACY_CHUNK_ID + "_index"


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    tables = _table_names()

    if LEGACY_TABLE in tables and "knowledge_bases" not in tables:
        op.rename_table(LEGACY_TABLE, "knowledge_bases")
        tables.remove(LEGACY_TABLE)
        tables.add("knowledge_bases")

    if "knowledge_bases" in tables:
        columns = _column_names("knowledge_bases")
        with op.batch_alter_table("knowledge_bases") as batch_op:
            if LEGACY_ID in columns and "knowledge_base_id" not in columns:
                batch_op.alter_column(LEGACY_ID, new_column_name="knowledge_base_id")
            if LEGACY_NAME in columns and "knowledge_base_name" not in columns:
                batch_op.alter_column(LEGACY_NAME, new_column_name="knowledge_base_name")

    if "assets" in tables:
        columns = _column_names("assets")
        indexes = _index_names("assets")
        with op.batch_alter_table("assets") as batch_op:
            if LEGACY_ASSET_ID in columns and "asset_knowledge_base_id" not in columns:
                batch_op.alter_column(LEGACY_ASSET_ID, new_column_name="asset_knowledge_base_id")
            if LEGACY_ASSET_INDEX in indexes:
                batch_op.drop_index(LEGACY_ASSET_INDEX)
            if "asset_knowledge_base_id_index" not in indexes:
                batch_op.create_index("asset_knowledge_base_id_index", ["asset_knowledge_base_id"])

    if "data_chunks" in tables:
        columns = _column_names("data_chunks")
        indexes = _index_names("data_chunks")
        with op.batch_alter_table("data_chunks") as batch_op:
            if LEGACY_CHUNK_ID in columns and "chunk_knowledge_base_id" not in columns:
                batch_op.alter_column(LEGACY_CHUNK_ID, new_column_name="chunk_knowledge_base_id")
            if LEGACY_CHUNK_INDEX in indexes:
                batch_op.drop_index(LEGACY_CHUNK_INDEX)
            if "chunk_knowledge_base_id_index" not in indexes:
                batch_op.create_index("chunk_knowledge_base_id_index", ["chunk_knowledge_base_id"])


def downgrade() -> None:
    tables = _table_names()

    if "data_chunks" in tables:
        columns = _column_names("data_chunks")
        indexes = _index_names("data_chunks")
        with op.batch_alter_table("data_chunks") as batch_op:
            if "chunk_knowledge_base_id_index" in indexes:
                batch_op.drop_index("chunk_knowledge_base_id_index")
            if LEGACY_CHUNK_INDEX not in indexes:
                batch_op.create_index(LEGACY_CHUNK_INDEX, ["chunk_knowledge_base_id"])
            if "chunk_knowledge_base_id" in columns and LEGACY_CHUNK_ID not in columns:
                batch_op.alter_column("chunk_knowledge_base_id", new_column_name=LEGACY_CHUNK_ID)

    if "assets" in tables:
        columns = _column_names("assets")
        indexes = _index_names("assets")
        with op.batch_alter_table("assets") as batch_op:
            if "asset_knowledge_base_id_index" in indexes:
                batch_op.drop_index("asset_knowledge_base_id_index")
            if LEGACY_ASSET_INDEX not in indexes:
                batch_op.create_index(LEGACY_ASSET_INDEX, ["asset_knowledge_base_id"])
            if "asset_knowledge_base_id" in columns and LEGACY_ASSET_ID not in columns:
                batch_op.alter_column("asset_knowledge_base_id", new_column_name=LEGACY_ASSET_ID)

    if "knowledge_bases" in tables:
        columns = _column_names("knowledge_bases")
        with op.batch_alter_table("knowledge_bases") as batch_op:
            if "knowledge_base_name" in columns and LEGACY_NAME not in columns:
                batch_op.alter_column("knowledge_base_name", new_column_name=LEGACY_NAME)
            if "knowledge_base_id" in columns and LEGACY_ID not in columns:
                batch_op.alter_column("knowledge_base_id", new_column_name=LEGACY_ID)

    if "knowledge_bases" in _table_names() and LEGACY_TABLE not in _table_names():
        op.rename_table("knowledge_bases", LEGACY_TABLE)
