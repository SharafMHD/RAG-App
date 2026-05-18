from fastapi import FastAPI
from routes import base, data, nlp
from helpers.config import get_settings
from stores.llm import LLMProvideFactory
from stores.vectordb import VectorDBProviderFactory
from contextlib import asynccontextmanager
from stores.llm.Templates.template_parser import TemplateParser
from sqlalchemy.ext.asyncio import create_async_engine , AsyncSession
from sqlalchemy.orm import sessionmaker
from utils.metrics import setup_metrics_endpoint

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup prometheus metrics endpoint
    setup_metrics_endpoint(app)
    app_settings = get_settings()
    postgres_conn = f"postgresql+asyncpg://{app_settings.POSTGRES_USER}:{app_settings.POSTGRES_PASSWORD}@{app_settings.POSTGRES_HOST}:{app_settings.POSTGRES_PORT}/{app_settings.POSTGRES_MAIN_DB}"
    app.db_engine = create_async_engine(postgres_conn, echo=False)
    
    app.db_client = sessionmaker(
        bind=app.db_engine,
        class_=AsyncSession,
        expire_on_commit=False)

    llm_provider_factory = LLMProvideFactory(app_settings)
    vectordb_provider_factory = VectorDBProviderFactory(config=app_settings, db_client=app.db_client)

    # Generation client
    app.generation_client = llm_provider_factory.create(provider=app_settings.GENERATION_BACKEND)
    app.generation_client.set_genration_model(app_settings.GENERATION_MODEL_ID)

    # Embedding client
    app.embedding_client = llm_provider_factory.create(provider=app_settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(app_settings.EMBEDDING_MODEL_ID, embedding_model_size=app_settings.EMBEDDING_MODEL_SIZE)

    # Vector DB client
    app.vector_db_client = vectordb_provider_factory.create(provider=app_settings.VECTOR_DB_BACKEND)
    await app.vector_db_client.connect()
    app.template_parser = TemplateParser(
        language=app_settings.PRIMARY_LANGUAGE,
        default_language=app_settings.DEFAULT_LANGUAGE
    )
    
    yield

    app.db_engine.dispose()
    await app.vector_db_client.disconnect()


#  Correct place to create the app
app = FastAPI(lifespan=lifespan)

#  Register all routers here
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
