
from fastapi import  Depends, APIRouter, status , Request
from fastapi.responses import JSONResponse
from helpers.config import get_settings, Settings
import logging
from routes.schemes.nlp import PushRequest , SearchRequest
from models.ProjectDataModel import ProjectDataModel
from models.ChunksDataModel import ChunkDataModel
from models import ResponseStatus
from controllers import NLPController
from uuid import UUID
from tqdm.auto import tqdm
from tasks.data_indexing import index_data_content

logger = logging.getLogger("uvicorn.error")
nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v1" , "NLP"],
)

@nlp_router.post("/index/push/{project_id}")
async def index_project( request: Request, project_id: UUID, push_request: PushRequest, app_settings: Settings = Depends(get_settings) ):
    # delay the indexing task to Celery
    task_result =  index_data_content.delay(project_id=project_id, 
                                                 do_reset=push_request.do_reset)
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, 
                        content={"status": True,
                                    "task_id": task_result.id,
                                    "message": ResponseStatus.Data_INDEXING_STARTED.value})


@nlp_router.get("/index/info/{project_id}")
async def get_index_info(request:Request, project_id: UUID):

    # Initialize models
    project_model = await ProjectDataModel.create_instance(db_client=request.app.db_client)
    # Get or create project
    project = await project_model.get_project_or_create(project_id)

        # Initialize NLP Controller
    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        vector_db_client=request.app.vector_db_client,
        template_parser=request.app.template_parser
    )

    collection_info = await nlp_controller.get_vector_db_collection_info(project=project)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
        "project_id": str(project_id), 
        "collection_info": collection_info,
        "message": ResponseStatus.NLP_INDEX_INFO_SUCCESS.value})

@nlp_router.post("/index/search/{project_id}")
async def search_index(request:Request, project_id: UUID, search_request: SearchRequest):

        # Initialize models
    project_model = await ProjectDataModel.create_instance(db_client=request.app.db_client)
    # Get or create project
    project = await project_model.get_project_or_create(project_id)

        # Initialize NLP Controller
    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        vector_db_client=request.app.vector_db_client,
        template_parser=request.app.template_parser
    )
    # Implement search logic here

    results = await nlp_controller.search_index(project=project , text=search_request.text , limit=search_request.limit)


    if not results:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "project_id": project_id, 
            "message": ResponseStatus.NLP_INDEX_SEARCH_ERROR.value})
    
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
        "project_id": str(project_id), 
        "results": [result.dict() for result in results],
        "message": ResponseStatus.NLP_INDEX_SEARCH_SUCCESS.value})
    
    
@nlp_router.post("/index/answer/{project_id}")
async def answer_rag(request:Request, project_id: UUID, search_request: SearchRequest):

        # Initialize models
    project_model = await ProjectDataModel.create_instance(db_client=request.app.db_client)
    # Get or create project
    project = await project_model.get_project_or_create(project_id)

        # Initialize NLP Controller
    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        vector_db_client=request.app.vector_db_client,
        template_parser=request.app.template_parser
    )
    answer, full_prompt, chat_history = await nlp_controller.answer_rag_query(
        project=project , 
        query_text=search_request.text , 
        limit=search_request.limit
    )
    if not answer:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "project_id": project_id, 
            "message": ResponseStatus.NLP_RAG_ANSWER_ERROR.value})
        
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
        "project_id": str(project_id),
        "answer": answer,
        "full_prompt": full_prompt,
        "chat_history": chat_history,
        "message": ResponseStatus.NLP_RAG_ANSWER_SUCCESS.value})