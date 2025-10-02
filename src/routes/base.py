from fastapi import APIRouter, Depends
from helpers import get_settings, Settings


base_router = APIRouter(
    prefix="/api/v1",
    tags=["Base"],
)
@base_router.get("/welcome")
async def welcome_message(app_settings: Settings=Depends(get_settings)):

    return {"message": "Welcome to the RAG-APP 2!",
            "app_name": app_settings.APP_NAME,
            "version": app_settings.APP_VERSION,
            "environment": app_settings.ENVIRONMENT}