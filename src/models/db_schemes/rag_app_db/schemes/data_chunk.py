from .rag_app_db_base import SQLAlchemyBase
from sqlalchemy import Column, Index, Integer, String, DateTime ,ForeignKey, func 
from sqlalchemy.dialects.postgresql import UUID ,JSONB
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from typing import Any
import uuid 


class DataChunk(SQLAlchemyBase):
    __tablename__ = "data_chunks"

    chunk_id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4, unique=True, nullable=False)
    chunk_asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.asset_id"), nullable=False)  # Foreign key to assets.asset_id
    chunk_knowledge_base_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bases.knowledge_base_id"), nullable=False)  # Foreign key to knowledge_bases.knowledge_base_id

    chunk_content = Column(String, nullable=False)  # Store the actual content of the chunk
    chunk_metadata = Column(JSONB, nullable=True)  # Store metadata as JSON
    chunk_order = Column(Integer, nullable=False)  # Order of the chunk within the asset
    chunking_strategy = Column(String, nullable=True)
    embedding_model = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
    parent_chunk_id = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True, onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), server_default=func.now(),nullable=True)

    # define asset relationship
    asset = relationship("Asset", back_populates="data_chunks")
    # define knowledge_base relationship
    knowledge_base = relationship("KnowledgeBase", back_populates="data_chunks")

    # define indexes
    __table_args__ = (
        # Index on chunk_asset_id for faster lookups      
        Index("chunk_asset_id_index", "chunk_asset_id"),
        # Index on chunk_knowledge_base_id for faster lookups       
         Index("chunk_knowledge_base_id_index", "chunk_knowledge_base_id"),
         Index("chunk_content_hash_index", "content_hash"),
    )

class RetrievedDocuments(BaseModel):
    text: str
    score: float
    chunk_id: str | None = None
    source: str | None = None
    page_number: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieval_mode: str | None = None