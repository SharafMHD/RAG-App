from .rag_app_db_base import SQLAlchemyBase
from sqlalchemy import Column, Index, Integer, String, DateTime ,ForeignKey, func 
from sqlalchemy.dialects.postgresql import UUID ,JSONB
from sqlalchemy.orm import relationship
import uuid  


class Asset(SQLAlchemyBase):
    __tablename__ = "assets"

    #asset_id = Column(Integer, primary_key=True, index=True , autoincrement=True)
    asset_id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4, unique=True, nullable=False)
    asset_project_id = Column(UUID(as_uuid=True), ForeignKey("projects.project_id"), nullable=False)  # Foreign key to projects.project_id



    asset_name = Column(String, unique=True, nullable=False)
    asset_type = Column(String, nullable=False)
    asset_size = Column(Integer, nullable=False)
    asset_config = Column(String, nullable=True)  # Store JSON as string
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True, onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), server_default=func.now(),nullable=True)


    # definfe projcect relationship
    project = relationship("Project", back_populates="assets")
    # define data_chunks relationship
    data_chunks = relationship("DataChunk", back_populates="asset", cascade="all, delete-orphan")

    # define indexes
    __table_args__ = (
        # Index on asset_project_id for faster lookups      
        Index("asset_project_id_index", "asset_project_id"),
        # Index on asset_type for faster lookups       
         Index("asset_type_index", "asset_type"),
    )