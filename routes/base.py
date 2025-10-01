from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
import os

load_dotenv(".env")

base_router = APIRouter(
    prefix="/api/v1",
    tags=["Base"],
)

@base_router.get("/welcome")
async def welcome_message():
    return {"message": "Welcome to the RAG-APP 2!",
            "app_name": os.getenv("APP_NAME", "RAG-APP"),
            "version": os.getenv("APP_VERSION", "1.0.0"),
            "environment": os.getenv("ENVIRONMENT", "development")}