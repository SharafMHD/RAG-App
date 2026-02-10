from .rag_app_db_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, String, DateTime , func
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

class Project(SQLAlchemyBase):
    __tablename__ = "projects"

    project_id = Column(Integer, primary_key=True, index=True , autoincrement=True)
    project_uuid = Column(UUID(as_uuid=True), default=UUID.uuid4, unique=True, nullable=False)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True, onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), server_default=func.now(),nullable=True)
    owner = Column(String, nullable=False)
    