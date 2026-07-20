import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import select, delete
from models.db_schemes.rag_app_db.schemes.celery_task_executions import celery_task_executions

logger = logging.getLogger("celery.task")

class IdempotencyManager:

    def __init__(self, db_client, knowledge_base_id=None):
        """
        Initialize the Idempotency Manager.
        Reuses the global AsyncSession factory pool wrapper.
        """
        self.db_client = db_client
        self.knowledge_base_id = knowledge_base_id

    def generate_task_args_hash(self, task_name: str, task_args: dict) -> str:
        """Generate a deterministic SHA256 hash for task arguments."""
        task_string = f"{task_name}:{json.dumps(task_args, sort_keys=True, default=str)}"
        return hashlib.sha256(task_string.encode()).hexdigest()
    
    async def create_task_execution_record(self, task_name: str, task_args: dict, celery_task_id: UUID) -> celery_task_executions:
        """Create a new tracking record asynchronously."""
        arg_hash = self.generate_task_args_hash(task_name, task_args)
        
        new_execution_record = celery_task_executions(
            task_name=task_name,
            task_args_hash=arg_hash,
            celery_task_id=celery_task_id,
            status="PENDING",
            task_args=task_args,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        
        async with self.db_client() as session:
            session.add(new_execution_record)
            await session.commit()
            await session.refresh(new_execution_record)
            session.expunge(new_execution_record)  # Safe across multi-file scope calls
            
        return new_execution_record

    async def update_task_execution_status(self, execution_id: UUID, status: str, result: dict = None) -> celery_task_executions:
        """Updates task state using native Async SQL 2.0 select structures."""
        async with self.db_client() as session:
            stmt = select(celery_task_executions).filter_by(execution_id=execution_id)
            db_result = await session.execute(stmt)
            execution_record = db_result.scalars().first()

            if not execution_record:
                raise ValueError(f"No task execution record found with execution_id: {execution_id}")
                
            execution_record.status = status
            if result is not None:
                execution_record.result = result
                
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
            
            if status == "STARTED":
                execution_record.started_at = current_time
            elif status == "PENDING":
                execution_record.started_at = None
            elif status in ["SUCCESS", "FAILURE"]:
                execution_record.completed_at = current_time
                
            await session.commit()
            await session.refresh(execution_record)
            session.expunge(execution_record)
            return execution_record

    async def get_existing_task_execution(self, task_name: str, task_args: dict) -> celery_task_executions | None:
        """Look up an existing execution record asynchronously."""
        arg_hash = self.generate_task_args_hash(task_name, task_args)
        async with self.db_client() as session:
            stmt = select(celery_task_executions).filter_by(
                task_args_hash=arg_hash, 
                task_name=task_name
            )
            db_result = await session.execute(stmt)
            record = db_result.scalars().first()
            if record:
                session.expunge(record)
            return record

    async def should_execute_task(self, task_name: str, task_args: dict, task_time_limit: int = 600) -> tuple[bool, celery_task_executions | None]:
        """Verify whether task parameters qualify for execution or lockouts."""
        existing_execution = await self.get_existing_task_execution(task_name, task_args)

        if not existing_execution:
            return True, None

        if existing_execution.status == "SUCCESS":
            return False, existing_execution
            
        if existing_execution.status in ["PENDING", "STARTED", "RETRY"]:
            if existing_execution.started_at:
                time_elapsed = (datetime.now(timezone.utc).replace(tzinfo=None) - existing_execution.started_at).total_seconds()
                if time_elapsed > (task_time_limit + 60):
                    return True, existing_execution
            else:
                return True, existing_execution

            return False, existing_execution

        return True, existing_execution

    async def cleanup_old_records(self, days: int) -> int:
        """
        Deletes log tracking records older than the target timeframe 
        asynchronously using the async session client.
        """
        cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        async with self.db_client() as session:
            stmt = delete(celery_task_executions).where(celery_task_executions.created_at < cutoff_date)
            result = await session.execute(stmt)
            await session.commit()
            
            rows_deleted = result.rowcount
            logger.info("Successfully dropped %d outdated execution logs from DB.", rows_deleted)
            return rows_deleted
