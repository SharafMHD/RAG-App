from fastapi import  Depends, APIRouter, status , Request
from fastapi.responses import JSONResponse
from helpers.config import get_settings, Settings
import logging
from routes.schemes.nlp import PushRequest
from models.ProjectDataModel import ProjectDataModel
from models.ChunksDataModel import ChunkDataModel
from models import ResponseStatus
from controllers import NLPController

logger = logging.getLogger("uvicorn.error")
nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v1" , "nlp"],
)

@nlp_router.post("/index/push/{project_id}")
async def index_project(request:Request, project_id:str, push_request: PushRequest , app_settings: Settings=Depends(get_settings)):
    # Initialize models
    project_model = await ProjectDataModel.create_instance(db_client=request.app.mongodb_client)
    chunck_model = await ChunkDataModel.create_instance(db_client=request.app.mongodb_client)
    # Get or create project
    project = await project_model.get_project_or_create(project_id)
    # Validate project existence
    if not project:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": False, 
            "project_id": project_id, 
            "message": ResponseStatus.PROJECT_NOT_FOUND_ERROR.value})
    # Initialize NLP Controller
    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.emedding_client,
        vector_db_client=request.app.vector_db_client
    )
    # Retrieve data chunks for the project
    has_records = False
    page_no = 1
    indexed_chunks_count = 0

    while has_records:
        page_chunks = await chunck_model.get_data_chunks_by_project(project.id, page_no)
        if len(page_chunks):
           page_no += 1
        
        if not len(page_chunks) or len(page_chunks) == 0:
            has_records = False
            break

    # Process chunks for indexing
    is_indexed = await nlp_controller.index_into_vector_db(
            project=project,
            data_chunks=page_chunks,
            do_reset=push_request.do_reset
    )

    if is_indexed:
        indexed_chunks_count += len(page_chunks)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
            "project_id": project_id, 
            "indexed_chunks_count": indexed_chunks_count,
            "message": ResponseStatus.NLP_INDEXING_SUCCESS.value})
    else:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "project_id": project_id, 
            "message": ResponseStatus.NLP_INDEXING_ERROR.value})


