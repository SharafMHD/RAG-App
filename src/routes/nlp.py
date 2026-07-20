
from fastapi import  Depends, APIRouter, status , Request
from fastapi.responses import JSONResponse
from helpers.config import get_settings, Settings
import logging
from routes.schemes.nlp import PushRequest , SearchRequest
from models.KnowledgeBaseDataModel import KnowledgeBaseDataModel
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

@nlp_router.post("/index/push/{knowledge_base_id}")
async def index_knowledge_base( request: Request, knowledge_base_id: UUID, push_request: PushRequest, app_settings: Settings = Depends(get_settings) ):
    # delay the indexing task to Celery
    task_result =  index_data_content.delay(knowledge_base_id=knowledge_base_id, 
                                                 do_reset=push_request.do_reset)
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, 
                        content={"status": True,
                                    "task_id": task_result.id,
                                    "message": ResponseStatus.Data_INDEXING_STARTED.value})


@nlp_router.get("/index/info/{knowledge_base_id}")
async def get_index_info(request:Request, knowledge_base_id: UUID):

    # Initialize models
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    # Get or create knowledge_base
    knowledge_base = await knowledge_base_model.get_knowledge_base_or_create(knowledge_base_id)

        # Initialize NLP Controller
    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        vector_db_client=request.app.vector_db_client,
        template_parser=request.app.template_parser
    )

    collection_info = await nlp_controller.get_vector_db_collection_info(knowledge_base=knowledge_base)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
        "knowledge_base_id": str(knowledge_base_id), 
        "collection_info": collection_info,
        "message": ResponseStatus.NLP_INDEX_INFO_SUCCESS.value})

@nlp_router.post("/index/search/{knowledge_base_id}")
async def search_index(request:Request, knowledge_base_id: UUID, search_request: SearchRequest):

        # Initialize models
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    # Get or create knowledge_base
    knowledge_base = await knowledge_base_model.get_knowledge_base_or_create(knowledge_base_id)

        # Initialize NLP Controller
    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        vector_db_client=request.app.vector_db_client,
        template_parser=request.app.template_parser
    )
    # Implement search logic here

    results = await nlp_controller.search_index(knowledge_base=knowledge_base , text=search_request.text , limit=search_request.limit)


    if not results:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "knowledge_base_id": str(knowledge_base_id), 
            "message": ResponseStatus.NLP_INDEX_SEARCH_ERROR.value})
    
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
        "knowledge_base_id": str(knowledge_base_id), 
        "results": [result.dict() for result in results],
        "message": ResponseStatus.NLP_INDEX_SEARCH_SUCCESS.value})
    
    
@nlp_router.post("/index/answer/{knowledge_base_id}")
async def answer_rag(request:Request, knowledge_base_id: UUID, search_request: SearchRequest):

        # Initialize models
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    # Get or create knowledge_base
    knowledge_base = await knowledge_base_model.get_knowledge_base_or_create(knowledge_base_id)

        # Initialize NLP Controller
    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        vector_db_client=request.app.vector_db_client,
        template_parser=request.app.template_parser
    )
    answer, full_prompt, chat_history = await nlp_controller.answer_rag_query(
        knowledge_base=knowledge_base , 
        query_text=search_request.text , 
        limit=search_request.limit
    )
    if not answer:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "knowledge_base_id": str(knowledge_base_id), 
            "message": ResponseStatus.NLP_RAG_ANSWER_ERROR.value})
        
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
        "knowledge_base_id": str(knowledge_base_id),
        "answer": answer,
        "full_prompt": full_prompt,
        "chat_history": chat_history,
        "message": ResponseStatus.NLP_RAG_ANSWER_SUCCESS.value})