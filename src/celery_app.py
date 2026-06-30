from celery import Celery
from helpers.config import get_settings

settings = get_settings()

# Initialize Celery
celery_app = Celery(
    "rag_app",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Configure Celery
celery_app.conf.update(
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_TASK_SERIALIZER,
    accept_content=[settings.CELERY_TASK_SERIALIZER],
    # Set the task time limit and other configurations
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    # Acknowledge tasks late to ensure they are not lost if a worker crashes
    task_acks_late=settings.CELERY_TASK_ACKS_LATE,
    # Set the number of concurrent worker processes
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    # Set the result expiration time (in seconds) for completed tasks
    task_ignore_result=False,
    task_result_expires=3600,  # Result expires in 1 hour
    # conection settings for better performance and reliability
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    worker_cancel_long_running_tasks_on_connection_loss=True,
)

celery_app.conf.task_default_queue = "default"