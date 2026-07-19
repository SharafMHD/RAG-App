from fastapi import UploadFile, Depends, APIRouter, status , Request
from fastapi.responses import JSONResponse
from models import ResponseStatus
from helpers.config import get_settings, Settings
from controllers import DataController 
import logging
import aiofiles
import os
from uuid import UUID
from routes.schemes.data import ProcessRequest ,ProjectData
from models.ProjectDataModel import ProjectDataModel
from models.AssetModel import AssetModel
from models.db_schemes import Project , Asset 
from models.enums.AssetTypeEnum import AssetTypeEnum
from tasks.file_processing import process_project_files
from tasks.process_workflow import process_and_index_workflow

logger = logging.getLogger("uvicorn.error")
data_router = APIRouter(
        prefix="/api/v1/data",
        tags=["api_v1" , "Data"],
    )
# Define the endpoint for creating a new project
@data_router.post("/projects/create")
async def create_project(request:Request, project_data: ProjectData):
    project_model = await ProjectDataModel.create_instance(db_client=request.app.db_client)
    Projectobject = Project(    
        project_name= project_data.project_name,
        description= project_data.description,
        owner= project_data.owner
    )
    new_project = await project_model.create_project(project_data=Projectobject)
    if new_project:
         return JSONResponse(
        status_code=status.HTTP_201_CREATED, 
        content={
            "status": True, 
            # Convert UUID to string here
            "project_id": str(new_project.project_id), 
            "project_name": new_project.project_name, 
            "description": new_project.description, 
            "owner": new_project.owner,
            "message": ResponseStatus.PROJECT_CREATED_SUCCESS.value
        }
    )
    else:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "project_name": project_data.project_name, 
            "description": project_data.description, 
            "owner": project_data.owner,
            "message": ResponseStatus.PROJECT_CREATED_ERROR.value})
# Define the endpoint for uploading a file to a project
@data_router.post("/upload/{project_id}")
async def upload_file(request:Request,project_id: UUID, file: UploadFile , app_settings: Settings=Depends(get_settings)):
    project_model = await ProjectDataModel.create_instance(db_client=request.app.db_client)
    new_project = await project_model.get_project_or_create(project_id)
    # validate file type and size
    controller = DataController()
    is_valid, response_status = controller.validate_uploded_file(file)
     # if file is not valid return error response
    if not is_valid:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": is_valid, 
            "project_id": project_id, 
            "file_name": file.filename,
            "file_type": file.content_type, 
            "file_size": file.size, 
            "message": response_status})
    #project_dir_path = ProjectController().get_project_path(project_id)
    file_path , file_id = controller.generate_unique_filepath(original_filename=file.filename, project_id=project_id)
    # save file to disk
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):  # Read file in chunks
                await f.write(chunk)
        await file.close()
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "project_id": new_project.project_id, 
            "file_name": file.filename,
            "file_type": file.content_type, 
            "file_size": file.size, 
            "message": ResponseStatus.FILE_UPLOAD_ERROR.value})

    # Store Asset metadata in the database
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    logger.info(f"Storing asset metadata for file: {file.filename}, project_id: {project_id}, file_path: {file_path}. file_size: {os.path.getsize(file_path)} bytes")
    asset_resource = Asset(
            asset_project_id= new_project.project_id,
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
@data_router.post("/processfile/{project_id}")
async def process_file(request:Request,project_id: UUID, process_request: ProcessRequest):
   
   # file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    # Delegate the file processing task to Celery
    task = process_project_files.delay(
        project_id=project_id,
        file_id=process_request.file_id,
        chunk_size=chunk_size,
        overlap_size=overlap_size,
        do_reset=do_reset
    )

    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": True,
        "task_id": task.id,
        "message": ResponseStatus.FILE_PROCESSING_STARTED.value})
# Define the endpoint for processing and indexing a file into chunks
@data_router.post("/process_and_index/{project_id}")
async def process_and_index(request:Request,project_id: UUID, process_request: ProcessRequest):
   
   # file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    # Delegate the file processing task to Celery
    workflow_task = process_and_index_workflow.delay(
        project_id=project_id,
        file_id=process_request.file_id,
        chunk_size=chunk_size,
        overlap_size=overlap_size,
        do_reset=do_reset
    )

    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": True,
        "workflow_task_id": workflow_task.id,
        "message": ResponseStatus.FILE_PROCESSING_STARTED.value})

   