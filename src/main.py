from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from routes import base, data, nlp
from helpers.config import get_settings
from stores.llm import LLMProvideFactory
from stores.vectordb import VectorDBProviderFactory
from stores.llm.Templates.template_parser import TemplateParser
from utils.metrics import setup_metrics_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_settings = get_settings()

    postgres_conn = (
        f"postgresql+asyncpg://"
        f"{app_settings.POSTGRES_USER}:"
        f"{app_settings.POSTGRES_PASSWORD}@"
        f"{app_settings.POSTGRES_HOST}:"
        f"{app_settings.POSTGRES_PORT}/"
        f"{app_settings.POSTGRES_MAIN_DB}"
    )

    app.db_engine = create_async_engine(postgres_conn, echo=False)

    app.db_client = sessionmaker(
        bind=app.db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    llm_provider_factory = LLMProvideFactory(app_settings)

    vectordb_provider_factory = VectorDBProviderFactory(
        config=app_settings,
        db_client=app.db_client,
    )

    app.generation_client = llm_provider_factory.create(
        provider=app_settings.GENERATION_BACKEND
    )
    app.generation_client.set_genration_model(
        app_settings.GENERATION_MODEL_ID
    )

    app.embedding_client = llm_provider_factory.create(
        provider=app_settings.EMBEDDING_BACKEND
    )
    app.embedding_client.set_embedding_model(
        app_settings.EMBEDDING_MODEL_ID,
        embedding_model_size=app_settings.EMBEDDING_MODEL_SIZE,
    )

    app.vector_db_client = vectordb_provider_factory.create(
        provider=app_settings.VECTOR_DB_BACKEND
    )
    await app.vector_db_client.connect()

    app.template_parser = TemplateParser(
        language=app_settings.PRIMARY_LANGUAGE,
        default_language=app_settings.DEFAULT_LANGUAGE,
    )

    yield

    await app.db_engine.dispose()
    await app.vector_db_client.disconnect()


app = FastAPI(lifespan=lifespan)

setup_metrics_endpoint(app)

app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)