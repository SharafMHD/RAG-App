from fastapi import UploadFile, Depends, APIRouter , status
from fastapi.responses import JSONResponse
from helpers import get_settings , Settings
from controllers import DataController

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["Base" , "Data"],
)
@data_router.post("/upload/{project_id}")
async def upload_file(project_id:str, file: UploadFile , app_settings: Settings=Depends(get_settings)):
    
    # validate file type and size
    is_valid , ResponseStatus = DataController().validate_uploded_file(file)
    if not is_valid:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": is_valid, 
            "project_id": project_id, 
            "file_name": file.filename,
            "file_type": file.content_type, 
            "file_size": file.size, 
            "message": ResponseStatus})


