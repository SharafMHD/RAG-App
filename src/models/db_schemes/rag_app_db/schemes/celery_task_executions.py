from .rag_app_db_base import SQLAlchemyBase
from sqlalchemy import Column, Index, Integer, String, DateTime ,ForeignKey, func 
from sqlalchemy.dialects.postgresql import UUID ,JSONB
from sqlalchemy.orm import relationship
import uuid  


class celery_task_executions(SQLAlchemyBase):
    __tablename__ = "celery_task_executions"

    execution_id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4, unique=True, nullable=False)
    task_name = Column(String(255), nullable=False)
    task_args_hash = Column(String(64), nullable=False) #SHA256 hash of the task arguments to uniquely identify the task execution
    celery_task_id = Column(UUID(as_uuid=True), nullable=False)  # Celery task ID for tracking
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, STARTED, SUCCESS, FAILURE
    task_args = Column(JSONB, nullable=True)  # Store task arguments as JSON
    result = Column(JSONB, nullable=True)  # Store task result as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True, onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)   
    started_at = Column(DateTime(timezone=True), nullable=True)  # Timestamp when the task started

    __table_args__ = (
        Index('ix_task_name_args_celery_id_hash', task_name, task_args_hash, celery_task_id, unique=True),  # Unique index on task_name and task_args_hash
        Index('ix_task_execution_status', status),  # Index on status for faster lookups
        Index('ix_task_created_at', created_at),  # Index on created_at for faster lookups
        Index('ix_celery_task_id', celery_task_id),  # Index on celery_task_id for faster lookups
    )   
