from fastapi import FastAPI
from routes import base , data
from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import get_settings

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app_settings = get_settings()
    app.mongodb_client = AsyncIOMotorClient(app_settings.MONGODB_URL)
    app.mongodb = app.mongodb_client[app_settings.MONGODB_DB_NAME]
    yield
    app.mongodb_client.close()


app = FastAPI(lifespan=lifespan)

app.include_router(base.base_router)
app.include_router(data.data_router)
