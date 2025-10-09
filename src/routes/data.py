from fastapi import UploadFile, Depends, APIRouter, status , Request
from fastapi.responses import JSONResponse
from models import ResponseStatus
from helpers.config import get_settings, Settings
from controllers import DataController , ProcessFileController
import logging
import aiofiles
from routes.schemes.data import ProcessRequest
from models.ProjectDataModel import ProjectDataModel
from models.ChunksDataModel import ChunkDataModel

from models.db_schemes import DataChunk

logger = logging.getLogger("uvicorn.error")
data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["Base" , "Data"],
)
@data_router.post("/upload/{project_id}")
async def upload_file(request:Request,project_id:str, file: UploadFile , app_settings: Settings=Depends(get_settings)):
    project_model = await ProjectDataModel.create_instance(db_client=request.app.mongodb_client)
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
            "project_id": new_project.id, 
            "file_name": file.filename,
            "file_type": file.content_type, 
            "file_size": file.size, 
            "message": ResponseStatus.FILE_UPLOAD_ERROR.value})

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
        "file_name": file.filename,
        "file_type": file.content_type, 
        "file_size": file.size, 
        "file_id": file_id,
        "message": ResponseStatus.FILE_UPLODED_SUCCESS.value})

@data_router.post("/processfile/{project_id}")
async def process_file(request:Request,project_id:str, process_request: ProcessRequest):
    file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    project_model = await ProjectDataModel.create_instance(db_client=request.app.mongodb_client)
    project = await project_model.get_project_or_create(project_id)

    chunk_model =await  ChunkDataModel.create_instance(db_client=request.app.mongodb_client)

    process_file_controller = ProcessFileController(project_id)
    file_content = process_file_controller.get_document_content(file_id)
    file_chunks = process_file_controller.process_file(file_content, chunk_size, overlap_size)
    file_chunks_records = [ 
        DataChunk(
                chunk_text=chunk.page_content,
                chunk_metadata= chunk.metadata,
                chunk_order= i+1,
                chunk_project_id=str(project.id)
            )
        for i, chunk in enumerate(file_chunks)
    ]
    
    """Validate if do reset is true delete all existing chunks for the project"""
    if do_reset:
        await chunk_model.delete_chunks_by_project(str(project.id))

    inserted_count = await chunk_model.bulk_insert_data_chunks(file_chunks_records)
    if not inserted_count:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "project_id": project_id, 
            "file_id": file_id,
            "inserted_count": inserted_count,
            "message": ResponseStatus.FILE_PROCESSING_ERROR.value})
    
    return {"status": True, "message": f"Processing file {file_id} for project {project_id} with chunk size {chunk_size}, overlap size {overlap_size}, reset={do_reset}" , "chunks_count": len(file_chunks), "chunks": file_chunks}

