import logging
from celery import Celery
from helpers.config import get_settings
from stores.llm import LLMProvideFactory
from stores.vectordb import VectorDBProviderFactory
from stores.llm.Templates.template_parser import TemplateParser

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger("celery.app")
settings = get_settings()

async def get_setup_utilites():
    """
    Creates and setups connections completely INSIDE the task's 
    running event loop, preventing cross-loop runtime errors.
    """
    postgres_conn = (
        f"postgresql+asyncpg://"
        f"{settings.POSTGRES_USER}:"
        f"{settings.POSTGRES_PASSWORD}@"
        f"{settings.POSTGRES_HOST}:"
        f"{settings.POSTGRES_PORT}/"
        f"{settings.POSTGRES_MAIN_DB}"
    )
    
    # Initialize engine and sessionmaker safely inside the active task loop context
    db_engine = create_async_engine(postgres_conn, echo=False)
    db_client = sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    llm_provider_factory = LLMProvideFactory(settings)
    vectordb_provider_factory = VectorDBProviderFactory(
        config=settings,
        db_client=db_client,
    )

    generation_client = llm_provider_factory.create(provider=settings.GENERATION_BACKEND)
    generation_client.set_genration_model(settings.GENERATION_MODEL_ID)

    embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    embedding_client.set_embedding_model(
        settings.EMBEDDING_MODEL_ID,
        embedding_model_size=settings.EMBEDDING_MODEL_SIZE,
    )

    vector_db_client = vectordb_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
    await vector_db_client.connect()

    template_parser = TemplateParser(
        language=settings.PRIMARY_LANGUAGE,
        default_language=settings.DEFAULT_LANGUAGE,
    )

    return (
        db_engine, 
        db_client, 
        llm_provider_factory, 
        vectordb_provider_factory, 
        generation_client, 
        embedding_client, 
        vector_db_client, 
        template_parser
    )


# ==============================================================================
# CELERY SYSTEM CONFIGURATION
# ==============================================================================
celery_app = Celery(
    "rag_app",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "tasks.file_processing", 
        "tasks.data_indexing",
        "tasks.process_workflow", 
        "tasks.celery_log_retention"
    ]
)

celery_app.conf.update(
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_TASK_SERIALIZER,
    accept_content=[settings.CELERY_TASK_SERIALIZER],
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_acks_late=settings.CELERY_TASK_ACKS_LATE,
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    task_ignore_result=False,
    task_result_expires=3600,
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    worker_cancel_long_running_tasks_on_connection_loss=True,

    task_routes={
        "tasks.file_processing.process_project_files": {"queue": "file_processing_queue"},
        "tasks.data_indexing.index_data_content": {"queue": "data_indexing_queue"},
        "tasks.process_workflow.process_and_index_workflow": {"queue": "file_processing_queue"},
        "tasks.celery_log_retention.clean_celery_task_executions": {"queue": "log_retention_queue"}
    },

    beat_schedule={
        "clean_celery_task_executions": {
            "task": "tasks.celery_log_retention.clean_celery_task_executions",
            "schedule": 86400,
            "args": (30,),
        }
    },
    timezone="asia/dubai"
)

celery_app.conf.task_default_queue = "default"
