from .rag_app_db_base import SQLAlchemyBase
from sqlalchemy import Column, Index, Integer, String, DateTime ,ForeignKey, func 
from sqlalchemy.dialects.postgresql import UUID ,JSONB
from sqlalchemy.orm import relationship
from pydantic import BaseModel
import uuid 


class DataChunk(SQLAlchemyBase):
    __tablename__ = "data_chunks"

    chunk_id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4, unique=True, nullable=False)
    chunk_asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.asset_id"), nullable=False)  # Foreign key to assets.asset_id
    chunk_project_id = Column(UUID(as_uuid=True), ForeignKey("projects.project_id"), nullable=False)  # Foreign key to projects.project_id

    chunk_content = Column(String, nullable=False)  # Store the actual content of the chunk
    chunk_metadata = Column(JSONB, nullable=True)  # Store metadata as JSON
    chunk_order = Column(Integer, nullable=False)  # Order of the chunk within the asset

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True, onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), server_default=func.now(),nullable=True)

    # define asset relationship
    asset = relationship("Asset", back_populates="data_chunks")
    # define project relationship
    project = relationship("Project", back_populates="data_chunks")

    # define indexes
    __table_args__ = (
        # Index on chunk_asset_id for faster lookups      
        Index("chunk_asset_id_index", "chunk_asset_id"),
        # Index on chunk_project_id for faster lookups       
         Index("chunk_project_id_index", "chunk_project_id"),
    )

class RetrievedDocuments(BaseModel):
    text: str
    score: float