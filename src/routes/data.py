from fastapi import UploadFile, Depends, APIRouter, status , Request, Query
from fastapi.responses import JSONResponse
from models import ResponseStatus
from helpers.config import get_settings, Settings
from controllers import DataController 
import logging
import aiofiles
import os
from uuid import UUID
from routes.schemes.data import ProcessRequest ,KnowledgeBaseData
from models.KnowledgeBaseDataModel import KnowledgeBaseDataModel
from models.AssetModel import AssetModel
from models.db_schemes import KnowledgeBase , Asset 
from models.enums.AssetTypeEnum import AssetTypeEnum
from tasks.file_processing import process_knowledge_base_files
from tasks.process_workflow import process_and_index_workflow

logger = logging.getLogger("uvicorn.error")
data_router = APIRouter(
        prefix="/api/v1/data",
        tags=["api_v1" , "Data"],
    )


@data_router.get("/knowledge-bases")
async def list_knowledge_bases(request: Request, page: int = Query(default=1, ge=1), page_size: int = Query(default=100, ge=1, le=500)):
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    knowledge_bases, total_pages, total_count = await knowledge_base_model.get_all_paged_knowledge_bases(page=page, page_size=page_size)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": True,
            "knowledge_bases": [
                {
                    "knowledge_base_id": str(knowledge_base.knowledge_base_id),
                    "knowledge_base_name": knowledge_base.knowledge_base_name,
                    "description": knowledge_base.description,
                    "owner": knowledge_base.owner,
                }
                for knowledge_base in knowledge_bases
            ],
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "total_count": total_count,
            "message": "Knowledge bases retrieved successfully",
        },
    )


# Define the endpoint for creating a new knowledge_base
@data_router.post("/knowledge-bases/create")
async def create_knowledge_base(request:Request, knowledge_base_data: KnowledgeBaseData):
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    KnowledgeBaseobject = KnowledgeBase(    
        knowledge_base_name= knowledge_base_data.knowledge_base_name,
        description= knowledge_base_data.description,
        owner= knowledge_base_data.owner
    )
    new_knowledge_base = await knowledge_base_model.create_knowledge_base(knowledge_base_data=KnowledgeBaseobject)
    if new_knowledge_base:
         return JSONResponse(
        status_code=status.HTTP_201_CREATED, 
        content={
            "status": True, 
            # Convert UUID to string here
            "knowledge_base_id": str(new_knowledge_base.knowledge_base_id), 
            "knowledge_base_name": new_knowledge_base.knowledge_base_name, 
            "description": new_knowledge_base.description, 
            "owner": new_knowledge_base.owner,
            "message": ResponseStatus.KNOWLEDGE_BASE_CREATED_SUCCESS.value
        }
    )
    else:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "knowledge_base_name": knowledge_base_data.knowledge_base_name, 
            "description": knowledge_base_data.description, 
            "owner": knowledge_base_data.owner,
            "message": ResponseStatus.KNOWLEDGE_BASE_CREATED_ERROR.value})
# Define the endpoint for uploading a file to a knowledge_base
@data_router.post("/upload/{knowledge_base_id}")
async def upload_file(request:Request,knowledge_base_id: UUID, file: UploadFile , app_settings: Settings=Depends(get_settings)):
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    new_knowledge_base = await knowledge_base_model.get_knowledge_base_or_create(knowledge_base_id)
    # validate file type and size
    controller = DataController()
    is_valid, response_status = controller.validate_uploded_file(file)
     # if file is not valid return error response
    if not is_valid:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": is_valid, 
            "knowledge_base_id": str(knowledge_base_id), 
            "file_name": file.filename,
            "file_type": file.content_type, 
            "file_size": file.size, 
            "message": response_status})
    #knowledge_base_dir_path = KnowledgeBaseController().get_knowledge_base_path(knowledge_base_id)
    file_path , file_id = controller.generate_unique_filepath(original_filename=file.filename, knowledge_base_id=knowledge_base_id)
    # save file to disk
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):  # Read file in chunks
                await f.write(chunk)
        await file.close()
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "knowledge_base_id": str(new_knowledge_base.knowledge_base_id), 
            "file_name": file.filename,
            "file_type": file.content_type, 
            "file_size": file.size, 
            "message": ResponseStatus.FILE_UPLOAD_ERROR.value})

    # Store Asset metadata in the database
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    logger.info(f"Storing asset metadata for file: {file.filename}, knowledge_base_id: {knowledge_base_id}, file_path: {file_path}. file_size: {os.path.getsize(file_path)} bytes")
    asset_resource = Asset(
            asset_knowledge_base_id= new_knowledge_base.knowledge_base_id,
            asset_name= file_id,
            asset_type= AssetTypeEnum.File.value,
            asset_size = os.path.getsize(file_path)
            )
    asset_record= await asset_model.create_asset(asset_resource)

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
        "file_name": file.filename,
        "file_type": file.content_type, 
        "file_size": file.size, 
        "file_id": file_id,
        "asset_id": str(asset_record.asset_id),
        "message": ResponseStatus.FILE_UPLODED_SUCCESS.value})
# Define the endpoint for processing a file into chunks
@data_router.post("/processfile/{knowledge_base_id}")
async def process_file(request:Request,knowledge_base_id: UUID, process_request: ProcessRequest):
   
   # file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    # Delegate the file processing task to Celery
    task = process_knowledge_base_files.delay(
        knowledge_base_id=knowledge_base_id,
        file_id=process_request.file_id,
        chunk_size=chunk_size,
        overlap_size=overlap_size,
        do_reset=do_reset
    )

    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": True,
        "task_id": task.id,
        "message": ResponseStatus.FILE_PROCESSING_STARTED.value})
# Define the endpoint for processing and indexing a file into chunks
@data_router.post("/process_and_index/{knowledge_base_id}")
async def process_and_index(request:Request,knowledge_base_id: UUID, process_request: ProcessRequest):
   
   # file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    # Delegate the file processing task to Celery
    workflow_task = process_and_index_workflow.delay(
        knowledge_base_id=knowledge_base_id,
        file_id=process_request.file_id,
        chunk_size=chunk_size,
        overlap_size=overlap_size,
        do_reset=do_reset
    )

    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": True,
        "workflow_task_id": workflow_task.id,
        "message": ResponseStatus.FILE_PROCESSING_STARTED.value})

   