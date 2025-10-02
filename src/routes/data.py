from fastapi import UploadFile, Depends, APIRouter , status
from fastapi.responses import JSONResponse
from helpers import get_settings , Settings
from controllers import DataController , ProjectController
import os
import aiofiles

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["Base" , "Data"],
)
@data_router.post("/upload/{project_id}")
async def upload_file(project_id:str, file: UploadFile , app_settings: Settings=Depends(get_settings)):
    
    # validate file type and size
    is_valid , ResponseStatus = DataController().validate_uploded_file(file)
    print(is_valid , ResponseStatus)
     # if file is not valid return error response
    if not is_valid:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": is_valid, 
            "project_id": project_id, 
            "file_name": file.filename,
            "file_type": file.content_type, 
            "file_size": file.size, 
            "message": ResponseStatus})
    project_dir_path = ProjectController().get_project_dir_path(project_id)
    file_path = os.path.join(project_dir_path , file.filename)
    print(file_path,app_settings.FILE_DEFAULT_CHUNK_SIZE)
    # save file to disk
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):  # Read file in chunks
            await f.write(chunk)
    await file.close()

    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
        "project_id": project_id, 
        "file_name": file.filename,
        "file_type": file.content_type, 
        "file_size": file.size, 
        "message": "File uploaded successfully"})



