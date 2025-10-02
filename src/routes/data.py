from fastapi import UploadFile, Depends, APIRouter, status
from fastapi.responses import JSONResponse
from models import ResponseStatus
from helpers.config import get_settings, Settings
from controllers import DataController
import logging
import aiofiles

logger = logging.getLogger("uvicorn.error")
data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["Base" , "Data"],
)
@data_router.post("/upload/{project_id}")
async def upload_file(project_id:str, file: UploadFile , app_settings: Settings=Depends(get_settings)):
    
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
        logger.error(f"Error saving file {file.filename} for project {project_id}: {e}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "project_id": project_id, 
            "file_name": file.filename,
            "file_type": file.content_type, 
            "file_size": file.size, 
            "message": ResponseStatus.FILE_UPLOAD_ERROR.value})

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
        "project_id": project_id, 
        "file_name": file.filename,
        "file_type": file.content_type, 
        "file_size": file.size, 
        "file_id": file_id,
        "message": ResponseStatus.FILE_UPLODED_SUCCESS.value})



