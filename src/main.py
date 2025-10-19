from fastapi import FastAPI
from routes import base , data, nlp
from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import get_settings
from stores.llm import LLMProvideFactory
from stores.vectordb import VectorDBProviderFactory
from routes import base , data
from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import get_settings

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app_settings = get_settings()
    app.mongodb_client = AsyncIOMotorClient(app_settings.MONGODB_URL)
    app.mongodb = app.mongodb_client[app_settings.MONGODB_DB_NAME]

    llm_provider_factory =LLMProvideFactory(app_settings)
    vectordb_provider_factory = VectorDBProviderFactory(app_settings)
    # Genration client
    app.generation_client= llm_provider_factory.create(provider=app_settings.GENERATION_BACKEND)
    app.generation_client.set_genration_model(app_settings.GENERATION_MODEL_ID)
    # Embedding client
    app.emedding_client = llm_provider_factory.create(provider=app_settings.EMBEDDING_BACKEND)
    app.emedding_client.set_embedding_model(app_settings.EMBEDDING_MODEL_ID, embedding_model_size=app_settings.EMBEDDING_MODEL_SIZE)
   
   # Vector DB client
    app.vector_db_client = vectordb_provider_factory.create(provider=app_settings.VECTOR_DB_BACKEND)
    app.vector_db_client.connect()
    yield
    app.mongodb_client.close()
    app.vector_db_client.disconnect()


    app = FastAPI(lifespan=lifespan)
    app.include_router(base.base_router)
    app.include_router(data.data_router)
    app.include_router(nlp.nlp_router)

    yield
    app.mongodb_client.close()


app = FastAPI(lifespan=lifespan)

app.include_router(base.base_router)
app.include_router(data.data_router)
