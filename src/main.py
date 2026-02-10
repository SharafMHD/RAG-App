from fastapi import FastAPI
from routes import base, data, nlp
from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import get_settings
from stores.llm import LLMProvideFactory
from stores.vectordb import VectorDBProviderFactory
from contextlib import asynccontextmanager
from stores.llm.Templates.template_parser import TemplateParser
from sqlalchemy.ext.asyncio import create_async_engine , AsyncSession
from sqlalchemy.orm import sessionmaker

@asynccontextmanager
async def lifespan(app: FastAPI):
    app_settings = get_settings()
    postgres_conn = f"postgresql+asyncpg://{app_settings.POSTGRESQL_USER}:{app_settings.POSTGRESQL_PASSWORD}@{app_settings.POSTGRESQL_HOST}:{app_settings.POSTGRESQL_PORT}/{app_settings.POSTGRESQL_DB_NAME}"
    app.db_engine = create_async_engine(postgres_conn, echo=True)
    
    app.db_client = sessionmaker(
        bind=app.db_engine,
        class_=AsyncSession,
        expire_on_commit=False)

    llm_provider_factory = LLMProvideFactory(app_settings)
    vectordb_provider_factory = VectorDBProviderFactory(app_settings)

    # Generation client
    app.generation_client = llm_provider_factory.create(provider=app_settings.GENERATION_BACKEND)
    app.generation_client.set_genration_model(app_settings.GENERATION_MODEL_ID)

    # Embedding client
    app.emedding_client = llm_provider_factory.create(provider=app_settings.EMBEDDING_BACKEND)
    app.emedding_client.set_embedding_model(app_settings.EMBEDDING_MODEL_ID, embedding_model_size=app_settings.EMBEDDING_MODEL_SIZE)

    # Vector DB client
    app.vector_db_client = vectordb_provider_factory.create(provider=app_settings.VECTOR_DB_BACKEND)
    app.vector_db_client.connect()
    app.template_parser = TemplateParser(
        language=app_settings.PRIMARY_LANGUAGE,
        default_language=app_settings.DEFAULT_LANGUAGE
    )
    
    yield

    app.db_engine.dispose()
    app.vector_db_client.disconnect()


# ✅ Correct place to create the app
app = FastAPI(lifespan=lifespan)

# ✅ Register all routers here
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
