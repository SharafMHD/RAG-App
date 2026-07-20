import asyncio
import logging

from celery_app import celery_app, get_setup_utilites
from utils.idempotencyManager import IdempotencyManager

logger = logging.getLogger("celery.task")


@celery_app.task(
    bind=True, 
    name="tasks.celery_log_retention.clean_celery_task_executions", 
    acks_late=True, 
    reject_on_worker_lost=True, 
    time_limit=3600, 
    soft_time_limit=3500
)
def clean_celery_task_executions(self, days: int = 30):
    """Celery task to clean up old task execution records."""
    return asyncio.run(_clean_celery_task_executions(self, days))


async def _clean_celery_task_executions(task_instance, days: int):
    db_engine = None
    vector_db_client = None

    try:
        (
            db_engine,
            db_client,
            llm_provider_factory,
            vectordb_provider_factory,
            generation_client,
            embedding_client,
            vector_db_client,
            template_parser,
        ) = await get_setup_utilites()

        idempotency_manager = IdempotencyManager(db_client=db_client)
        deleted_count = await idempotency_manager.cleanup_old_records(days=days)
        
        return {
            "status": True, 
            "message": f"Successfully cleaned up {deleted_count} records older than {days} days."
        }
    
    except Exception:
        logger.exception("An error occurred while cleaning up old task execution records.")
        raise
    finally:
        # Crucial: Clean up resources to prevent leaking connections
        try:
            if vector_db_client is not None:
                await vector_db_client.disconnect()
            if db_engine is not None:
                await db_engine.dispose()
        except Exception:
            logger.exception("An error occurred while cleaning up client resources.")
