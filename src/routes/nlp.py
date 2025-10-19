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
    tags=["api_v1" , "NLP"],
)

@nlp_router.post("/index/push/{project_id}")
async def index_project(request:Request, project_id:str, push_request: PushRequest , app_settings: Settings=Depends(get_settings)):
    # Initialize models
    project_model = await ProjectDataModel.create_instance(db_client=request.app.mongodb_client)
    chunck_model = await ChunkDataModel.create_instance(db_client=request.app.mongodb_client)
    # Get or create project
    project = await project_model.get_project_or_create(project_id)

    has_records = False
    page_no = 1
    indexed_chunks_count = 0
    idx=0 
    # Validate project existence
    if not project:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": False, 
            "project_id": project_id, 
            "message": ResponseStatus.PROJECT_NOT_FOUND_ERROR.value})
    else:
        has_records = True
    # Initialize NLP Controller
    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.emedding_client,
        vector_db_client=request.app.vector_db_client
    )
    # Retrieve data chunks for the project
    while has_records:
        page_chunks = await chunck_model.get_data_chunks_by_project(project.id, page_no)

        print(f"Processing page_no: {project.id} with {len(page_chunks)} chunks")
        if len(page_chunks):
           page_no += 1
        
        if not len(page_chunks) or len(page_chunks) == 0:
            has_records = False
            break

        # Process chunks for indexing
        chunks_ids= list(range(idx, idx + len(page_chunks)))
        idx += len(page_chunks)
        is_indexed =  nlp_controller.index_into_vector_db(
                project=project,
                data_chunks=page_chunks,
                do_reset=push_request.do_reset ,
                chunk_ids=chunks_ids
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

@nlp_router.get("/index/info/{project_id}")
async def get_index_info(request:Request, project_id: str):

    # Initialize models
    project_model = await ProjectDataModel.create_instance(db_client=request.app.mongodb_client)
    # Get or create project
    project = await project_model.get_project_or_create(project_id)

        # Initialize NLP Controller
    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.emedding_client,
        vector_db_client=request.app.vector_db_client
    )

    collection_info = nlp_controller.get_vector_db_collection_info(project=project)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
        "project_id": project_id, 
        "collection_info": collection_info,
        "message": ResponseStatus.NLP_INDEX_INFO_SUCCESS.value})

@nlp_router.get("/index/search/{project_id}")
async def search_index(request:Request, project_id: str, query: str):
