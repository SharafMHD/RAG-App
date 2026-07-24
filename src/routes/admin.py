import logging
import os
import shutil
from uuid import UUID

import aiofiles
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse

from controllers import DataController, NLPController
from controllers.KnowledgeBaseController import KnowledgeBaseController
from helpers.config import Settings, get_settings
from models import ResponseStatus
from models.AssetModel import AssetModel
from models.ChunksDataModel import ChunkDataModel
from models.KnowledgeBaseDataModel import KnowledgeBaseDataModel
from models.db_schemes import Asset, KnowledgeBase
from models.enums.AssetTypeEnum import AssetTypeEnum
from routes.schemes.data import KnowledgeBaseData, ProcessRequest
from celery.result import AsyncResult

from celery_app import celery_app
from tasks.process_workflow import process_and_index_workflow

logger = logging.getLogger("uvicorn.error")

admin_router = APIRouter(
    prefix="/api/v1/admin",
    tags=["api_v1", "Admin"],
)


@admin_router.post("/knowledge-bases/create")
async def admin_create_knowledge_base(request: Request, knowledge_base_data: KnowledgeBaseData):
    """Create a knowledge base from an admin route without auth/permission checks."""
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    knowledge_base = KnowledgeBase(
        knowledge_base_name=knowledge_base_data.knowledge_base_name,
        description=knowledge_base_data.description,
        owner=knowledge_base_data.owner or "admin",
    )
    new_knowledge_base = await knowledge_base_model.create_knowledge_base(knowledge_base_data=knowledge_base)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "status": True,
            "knowledge_base_id": str(new_knowledge_base.knowledge_base_id),
            "knowledge_base_name": new_knowledge_base.knowledge_base_name,
            "description": new_knowledge_base.description,
            "owner": new_knowledge_base.owner,
            "message": ResponseStatus.KNOWLEDGE_BASE_CREATED_SUCCESS.value,
        },
    )


@admin_router.post("/knowledge-bases/{knowledge_base_id}/process")
async def admin_process_knowledge_base(
    request: Request,
    knowledge_base_id: UUID,
    process_request: ProcessRequest,
):
    """Start process + index workflow for an existing knowledge base."""
    workflow_task = process_and_index_workflow.delay(
        knowledge_base_id=knowledge_base_id,
        file_id=process_request.file_id,
        chunk_size=process_request.chunk_size,
        overlap_size=process_request.overlap_size,
        do_reset=process_request.do_reset,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": True,
            "knowledge_base_id": str(knowledge_base_id),
            "workflow_task_id": workflow_task.id,
            "message": ResponseStatus.FILE_PROCESSING_STARTED.value,
        },
    )


@admin_router.post("/knowledge-bases/create-and-process")
async def admin_create_upload_process_knowledge_base(
    request: Request,
    file: UploadFile = File(...),
    knowledge_base_name: str = Form(...),
    description: str | None = Form(default=None),
    owner: str = Form(default="admin"),
    chunk_size: int = Form(default=900),
    overlap_size: int = Form(default=150),
    do_reset: bool = Form(default=True),
    app_settings: Settings = Depends(get_settings),
):
    """Create a knowledge base, upload one file, then start process + index workflow."""
    clean_name = knowledge_base_name.strip()
    if not clean_name:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"status": False, "message": "knowledge_base_name must not be blank"},
        )

    controller = DataController()
    is_valid, response_status = controller.validate_uploded_file(file)
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "status": False,
                "file_name": file.filename,
                "file_type": file.content_type,
                "file_size": file.size,
                "message": response_status,
            },
        )

    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    new_knowledge_base = await knowledge_base_model.create_knowledge_base(
        knowledge_base_data=KnowledgeBase(
            knowledge_base_name=clean_name,
            description=description,
            owner=owner,
        )
    )

    file_path, file_id = controller.generate_unique_filepath(
        original_filename=file.filename,
        knowledge_base_id=new_knowledge_base.knowledge_base_id,
    )
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
        await file.close()
    except Exception:
        logger.exception("Admin upload failed for knowledge_base_id=%s", new_knowledge_base.knowledge_base_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": False,
                "knowledge_base_id": str(new_knowledge_base.knowledge_base_id),
                "file_name": file.filename,
                "file_type": file.content_type,
                "file_size": file.size,
                "message": ResponseStatus.FILE_UPLOAD_ERROR.value,
            },
        )

    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    asset_record = await asset_model.create_asset(
        Asset(
            asset_knowledge_base_id=new_knowledge_base.knowledge_base_id,
            asset_name=file_id,
            asset_type=AssetTypeEnum.File.value,
            asset_size=os.path.getsize(file_path),
        )
    )

    workflow_task = process_and_index_workflow.delay(
        knowledge_base_id=new_knowledge_base.knowledge_base_id,
        file_id=file_id,
        chunk_size=chunk_size,
        overlap_size=overlap_size,
        do_reset=do_reset,
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": True,
            "knowledge_base_id": str(new_knowledge_base.knowledge_base_id),
            "knowledge_base_name": new_knowledge_base.knowledge_base_name,
            "description": new_knowledge_base.description,
            "owner": new_knowledge_base.owner,
            "file_name": file.filename,
            "file_id": file_id,
            "asset_id": str(asset_record.asset_id),
            "workflow_task_id": workflow_task.id,
            "message": "Knowledge base created, file uploaded, and processing/indexing started",
        },
    )


@admin_router.post("/knowledge-bases/{knowledge_base_id}/documents/upload-and-process")
async def admin_upload_process_document(
    request: Request,
    knowledge_base_id: UUID,
    file: UploadFile = File(...),
    chunk_size: int = Form(default=900),
    overlap_size: int = Form(default=150),
    do_reset: bool = Form(default=False),
    app_settings: Settings = Depends(get_settings),
):
    """Upload one document to an existing knowledge base and start process + index workflow."""
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    knowledge_base = await knowledge_base_model.get_knowledge_base_or_create(knowledge_base_id)

    controller = DataController()
    is_valid, response_status = controller.validate_uploded_file(file)
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": False, "file_name": file.filename, "file_type": file.content_type, "file_size": file.size, "message": response_status},
        )

    file_path, file_id = controller.generate_unique_filepath(original_filename=file.filename, knowledge_base_id=knowledge_base_id)
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
        await file.close()
    except Exception:
        logger.exception("Admin document upload failed for knowledge_base_id=%s", knowledge_base_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": False, "knowledge_base_id": str(knowledge_base_id), "file_name": file.filename, "message": ResponseStatus.FILE_UPLOAD_ERROR.value},
        )

    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    asset_record = await asset_model.create_asset(
        Asset(
            asset_knowledge_base_id=knowledge_base.knowledge_base_id,
            asset_name=file_id,
            asset_type=AssetTypeEnum.File.value,
            asset_size=os.path.getsize(file_path),
        )
    )
    workflow_task = process_and_index_workflow.delay(
        knowledge_base_id=knowledge_base.knowledge_base_id,
        file_id=file_id,
        chunk_size=chunk_size,
        overlap_size=overlap_size,
        do_reset=do_reset,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": True,
            "knowledge_base_id": str(knowledge_base.knowledge_base_id),
            "file_name": file.filename,
            "file_id": file_id,
            "asset_id": str(asset_record.asset_id),
            "workflow_task_id": workflow_task.id,
            "message": "Document uploaded and processing/indexing started",
        },
    )


@admin_router.get("/knowledge-bases/{knowledge_base_id}/documents")
async def admin_list_documents(
    request: Request,
    knowledge_base_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List documents/assets for a knowledge base with chunk counts."""
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    records, total_pages, total_count = await asset_model.get_paged_assets_with_chunk_counts(knowledge_base_id=knowledge_base_id, page=page, page_size=page_size)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": True,
            "knowledge_base_id": str(knowledge_base_id),
            "documents": [
                {
                    "asset_id": str(record["asset"].asset_id),
                    "file_id": record["asset"].asset_name,
                    "asset_type": record["asset"].asset_type,
                    "asset_size": record["asset"].asset_size,
                    "description": record["asset"].description,
                    "created_at": record["asset"].created_at.isoformat() if record["asset"].created_at else None,
                    "chunks_count": record["chunks_count"],
                }
                for record in records
            ],
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "total_count": total_count,
        },
    )


@admin_router.delete("/documents/{asset_id}")
async def admin_delete_document(request: Request, asset_id: UUID):
    """Delete one document, its chunks, file, and rebuild/drop related vector collection."""
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    chunk_model = await ChunkDataModel.create_instance(db_client=request.app.db_client)
    asset = await asset_model.get_asset_by_id(asset_id)
    if asset is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"status": False, "asset_id": str(asset_id), "message": "Document not found"})

    knowledge_base_id = asset.asset_knowledge_base_id
    file_path = os.path.join(KnowledgeBaseController().file_dir, str(knowledge_base_id), asset.asset_name)
    await chunk_model.delete_chunks_by_asset(asset_id)
    deleted = await asset_model.delete_asset_by_id(asset_id)
    if os.path.isfile(file_path):
        os.remove(file_path)

    vector_collection_rebuilt = False
    vector_collection_deleted = False
    try:
        knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
        knowledge_base = await knowledge_base_model.get_knowledge_base(knowledge_base_id)
        if knowledge_base is not None:
            nlp_controller = NLPController(
                generation_client=request.app.generation_client,
                embedding_client=request.app.embedding_client,
                vector_db_client=request.app.vector_db_client,
                template_parser=request.app.template_parser,
                db_client=request.app.db_client,
                settings=get_settings(),
            )
            await nlp_controller.reset_vector_db_collection(knowledge_base)
            remaining_chunks = await chunk_model.get_all_data_chunks_by_knowledge_base(knowledge_base_id)
            if remaining_chunks:
                vector_collection_rebuilt = bool(await nlp_controller.index_into_vector_db(knowledge_base, remaining_chunks, do_reset=True))
            else:
                vector_collection_deleted = True
    except Exception:
        logger.exception("Failed to rebuild vector collection after deleting asset_id=%s", asset_id)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": deleted,
            "asset_id": str(asset_id),
            "knowledge_base_id": str(knowledge_base_id),
            "deleted_file": not os.path.isfile(file_path),
            "deleted_chunks": True,
            "vector_collection_rebuilt": vector_collection_rebuilt,
            "vector_collection_deleted": vector_collection_deleted,
            "message": "Document and related chunks deleted",
        },
    )


@admin_router.get("/documents/{asset_id}/chunks")
async def admin_list_document_chunks(
    request: Request,
    asset_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List chunks related to one document/asset."""
    chunk_model = await ChunkDataModel.create_instance(db_client=request.app.db_client)
    chunks, total_pages, total_count = await chunk_model.get_paged_chunks_by_asset(asset_id=asset_id, page=page, page_size=page_size)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": True,
            "asset_id": str(asset_id),
            "chunks": [
                {
                    "chunk_id": str(chunk.chunk_id),
                    "chunk_asset_id": str(chunk.chunk_asset_id),
                    "chunk_knowledge_base_id": str(chunk.chunk_knowledge_base_id),
                    "chunk_order": chunk.chunk_order,
                    "chunk_content": chunk.chunk_content,
                    "chunk_metadata": chunk.chunk_metadata or {},
                    "chunking_strategy": chunk.chunking_strategy,
                    "embedding_model": chunk.embedding_model,
                    "content_hash": chunk.content_hash,
                    "parent_chunk_id": str(chunk.parent_chunk_id) if chunk.parent_chunk_id else None,
                }
                for chunk in chunks
            ],
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "total_count": total_count,
        },
    )


@admin_router.get("/tasks/{task_id}")
async def admin_get_task_status(task_id: str):
    """Return Celery task status for admin UI polling.

    process_and_index_workflow is a lightweight wrapper task that starts a chain.
    When the wrapper succeeds, follow its returned workflow_id so the UI reflects
    the actual processing/indexing task state instead of a premature SUCCESS.
    """
    task_result = AsyncResult(task_id, app=celery_app)
    result = task_result.result if task_result.ready() else None
    followed_task_id = task_id

    if isinstance(result, dict) and result.get("workflow_id"):
        followed_task_id = result["workflow_id"]
        task_result = AsyncResult(followed_task_id, app=celery_app)
        result = task_result.result if task_result.ready() else None

    if isinstance(result, Exception):
        result_payload = {"error": str(result)}
    else:
        result_payload = result
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": True,
            "task_id": task_id,
            "followed_task_id": followed_task_id,
            "state": task_result.state,
            "ready": task_result.ready(),
            "successful": task_result.successful() if task_result.ready() else False,
            "failed": task_result.failed(),
            "result": result_payload,
        },
    )


@admin_router.delete("/knowledge-bases/{knowledge_base_id}")
async def admin_delete_knowledge_base(request: Request, knowledge_base_id: UUID):
    """Delete a knowledge base plus related documents, chunks, uploaded files, and vector collection."""
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    deleted = await knowledge_base_model.delete_knowledge_base(knowledge_base_id)

    upload_dir = os.path.join(KnowledgeBaseController().file_dir, str(knowledge_base_id))
    if os.path.isdir(upload_dir):
        shutil.rmtree(upload_dir, ignore_errors=True)

    vector_collection_deleted = False
    vector_db_client = getattr(request.app, "vector_db_client", None)
    if vector_db_client is not None:
        collection_name = f"collection_{vector_db_client.default_vector_size}_{knowledge_base_id}".strip().replace(" ", "_").lower()
        try:
            if await vector_db_client.is_collection_exists(collection_name):
                await vector_db_client.drop_collection(collection_name)
                vector_collection_deleted = True
        except Exception:
            logger.exception("Failed to delete vector collection for knowledge_base_id=%s", knowledge_base_id)

    return JSONResponse(
        status_code=status.HTTP_200_OK if deleted else status.HTTP_404_NOT_FOUND,
        content={
            "status": deleted,
            "knowledge_base_id": str(knowledge_base_id),
            "deleted_documents_and_chunks": deleted,
            "deleted_upload_dir": not os.path.isdir(upload_dir),
            "deleted_vector_collection": vector_collection_deleted,
            "message": "Knowledge base deleted" if deleted else "Knowledge base not found",
        },
    )


@admin_router.get("/knowledge-bases")
async def admin_list_knowledge_bases(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
):
    """List knowledge bases from an admin route without auth/permission checks."""
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    records, total_pages, total_count = await knowledge_base_model.get_all_paged_knowledge_bases_with_stats(page=page, page_size=page_size)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": True,
            "knowledge_bases": [
                {
                    "knowledge_base_id": str(record["knowledge_base"].knowledge_base_id),
                    "knowledge_base_name": record["knowledge_base"].knowledge_base_name,
                    "description": record["knowledge_base"].description,
                    "owner": record["knowledge_base"].owner,
                    "documents_count": record["documents_count"],
                    "chunks_count": record["chunks_count"],
                    "kb_status": record["status"],
                }
                for record in records
            ],
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "total_count": total_count,
            "message": "Knowledge bases retrieved successfully",
        },
    )
