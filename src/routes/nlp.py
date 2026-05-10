
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

logger = logging.getLogger("uvicorn.error")
nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v1" , "NLP"],
)

@nlp_router.post("/index/push/{project_id}")
async def index_project(request:Request, project_id:UUID, push_request: PushRequest , app_settings: Settings=Depends(get_settings)):
    # Initialize models
    project_model = await ProjectDataModel.create_instance(db_client=request.app.db_client)
    chunck_model = await ChunkDataModel.create_instance(db_client=request.app.db_client)
    # Get or create project
    project = await project_model.get_project_or_create(project_id)
    nlp_controller = NLPController(
        vector_db_client= request.app.vector_db_client,
        generation_client= request.app.generation_client,
        embedding_client= request.app.embedding_client,
        template_parser= request.app.template_parser
    )
    
    has_records = False
    page_no = 1
    indexed_chunks_count = 0
    idx=0 

    # Create or reset vector db collection based on request
    collection_name =  nlp_controller.create_collection_name(str(project.project_id))
    _ = await request.app.vector_db_client.create_collection(
        collection_name= collection_name,
        embedding_size= request.app.embedding_client.embedd_size,
        do_reset= push_request.do_reset
        )

    # Validate project existence
    if not project:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status": False, 
            "project_id": project_id, 
            "message": ResponseStatus.PROJECT_NOT_FOUND_ERROR.value})
    else:
        has_records = True
        
        # Setup Batch processing
        total_chunks_count = await chunck_model.get_total_chunks_count_by_project(project.project_id)
        pbar = tqdm(total=total_chunks_count, desc="Indexing Chunks", position=0)

    
    # Retrieve data chunks for the project
    while has_records:
        page_chunks = await chunck_model.get_data_chunks_by_project(project.project_id, page_no)

        if len(page_chunks):
           page_no += 1
        
        if not len(page_chunks) or len(page_chunks) == 0:
            has_records = False
            break

        # Process chunks for indexing
        chunks_ids= list(range(idx, idx + len(page_chunks)))
        idx += len(page_chunks)
        is_indexed = await  nlp_controller.index_into_vector_db(
                project=project,
                data_chunks=page_chunks,
                do_reset=push_request.do_reset ,
                chunk_ids=chunks_ids
        )

        if is_indexed:
            pbar.update(len(page_chunks))
            indexed_chunks_count += len(page_chunks)
            return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
                "project_id": str(project_id), 
                "indexed_chunks_count": indexed_chunks_count,
                "message": ResponseStatus.NLP_INDEXING_SUCCESS.value})
        else:
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
                "project_id": str(project_id), 
                "message": ResponseStatus.NLP_INDEXING_ERROR.value})

@nlp_router.get("/index/info/{project_id}")
async def get_index_info(request:Request, project_id: UUID):

    # Initialize models
    project_model = await ProjectDataModel.create_instance(db_client=request.app.db_client)
    # Get or create project
    project = await project_model.get_project_or_create(project_id)

        # Initialize NLP Controller
    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.emedding_client,
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
        embedding_client=request.app.emedding_client,
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
        embedding_client=request.app.emedding_client,
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