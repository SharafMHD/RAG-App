from .rag_app_db_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, String, DateTime , func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

import uuid 

class Project(SQLAlchemyBase):
    __tablename__ = "projects"

   # project_id = Column(Integer, primary_key=True, index=True , autoincrement=True)
    project_id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4, unique=True, nullable=False)
    project_name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), server_default=func.now(),nullable=True)
    owner = Column(String, nullable=False)

    assets = relationship("Asset", back_populates="project", cascade="all, delete-orphan") 
    data_chunks = relationship("DataChunk", back_populates="project", cascade="all, delete-orphan")
    