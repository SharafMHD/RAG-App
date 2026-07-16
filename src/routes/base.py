import logging

from fastapi import APIRouter, Depends
from helpers import get_settings, Settings
import logging
logger = logging.getLogger("uvicorn.error")

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

# @base_router.get("/send_reports")
# async def send_reports(app_settings: Settings=Depends(get_settings)):
   
#     task = send_email.delay(
#         mail_wait_seonds=3
#     )
#     return {"message": "Reports sent successfully!",
#             "task_id": task.id,
#             "task_status": task.status}