import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
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


@base_router.get("/health/live", include_in_schema=False)
async def liveness_check():
    return {"status": "ok"}


@base_router.get("/health", include_in_schema=False)
async def readiness_check(request: Request):
    checks = {"database": "unknown", "vector_db": "unknown"}
    healthy = True

    try:
        async with request.app.db_client() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("Database health check failed")
        checks["database"] = "error"
        healthy = False

    try:
        vector_client = getattr(request.app, "vector_db_client", None)
        if vector_client is None:
            raise RuntimeError("Vector DB client is not initialized")
        checks["vector_db"] = "ok"
    except Exception:
        logger.exception("Vector DB health check failed")
        checks["vector_db"] = "error"
        healthy = False

    payload = {"status": "ok" if healthy else "error", "checks": checks}
    return JSONResponse(
        content=payload,
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
    )

# @base_router.get("/send_reports")
# async def send_reports(app_settings: Settings=Depends(get_settings)):
   
#     task = send_email.delay(
#         mail_wait_seonds=3
#     )
#     return {"message": "Reports sent successfully!",
#             "task_id": task.id,
#             "task_status": task.status}