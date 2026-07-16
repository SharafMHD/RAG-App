from celery import Celery
from helpers.config import get_settings

from helpers.config import get_settings
from stores.llm import LLMProvideFactory
from stores.vectordb import VectorDBProviderFactory
from stores.llm.Templates.template_parser import TemplateParser

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

settings = get_settings()

async def get_setup_utilites():

    # Database connection setup
    postgres_conn = (
        f"postgresql+asyncpg://"
        f"{settings.POSTGRES_USER}:"
        f"{settings.POSTGRES_PASSWORD}@"
        f"{settings.POSTGRES_HOST}:"
        f"{settings.POSTGRES_PORT}/"
        f"{settings.POSTGRES_MAIN_DB}"
    )
    # Create an asynchronous engine and sessionmaker for database interactions
    db_engine = create_async_engine(postgres_conn, echo=False)

    db_client = sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    # Initialize LLM and VectorDB provider factories
    llm_provider_factory = LLMProvideFactory(settings)

    vectordb_provider_factory = VectorDBProviderFactory(
        config=settings,
        db_client=db_client,
    )

    generation_client = llm_provider_factory.create(
        provider= settings.GENERATION_BACKEND
    )
    generation_client.set_genration_model(
        settings.GENERATION_MODEL_ID
    )

    embedding_client = llm_provider_factory.create(
        provider=settings.EMBEDDING_BACKEND
    )
    embedding_client.set_embedding_model(
        settings.EMBEDDING_MODEL_ID,
        embedding_model_size=settings.EMBEDDING_MODEL_SIZE,
    )

    vector_db_client = vectordb_provider_factory.create(
        provider=settings.VECTOR_DB_BACKEND
    )
    await vector_db_client.connect()

    template_parser = TemplateParser(
        language=settings.PRIMARY_LANGUAGE,
        default_language=settings.DEFAULT_LANGUAGE,
    )

    return (db_engine, db_client, llm_provider_factory,vectordb_provider_factory, generation_client, embedding_client, vector_db_client, template_parser)


# Initialize Celery
celery_app = Celery(
    "rag_app",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.file_processing"]  # Include the tasks module for Celery to discover tasks
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

    task_routes={
        "tasks.file_processing.process_project_files": {"queue": "file_processing_queue"}
    }
)

celery_app.conf.task_default_queue = "default"