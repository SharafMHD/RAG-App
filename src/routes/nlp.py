
from fastapi import  Depends, APIRouter, status , Request
from fastapi.responses import JSONResponse
from helpers.config import get_settings, Settings
import logging
from routes.schemes.nlp import (
    ChatAnswerResponse,
    Citation,
    PushRequest,
    RetrievalMetadata,
    SearchRequest,
    SourceChunk,
)
from models.KnowledgeBaseDataModel import KnowledgeBaseDataModel
from models.ChunksDataModel import ChunkDataModel
from models import ResponseStatus
from controllers import NLPController
from uuid import UUID, uuid4
from tqdm.auto import tqdm
from tasks.data_indexing import index_data_content

logger = logging.getLogger("uvicorn.error")
nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v1" , "NLP"],
)


def _metadata_value(metadata: dict, *keys: str):
    for key in keys:
        if key in metadata and metadata[key] is not None:
            return metadata[key]
    return None


def _build_chat_contract(knowledge_base_id: UUID, answer: str, retrieved_documents: list, limit: int, trace_id: str) -> ChatAnswerResponse:
    citations = []
    source_chunks = []
    scores = []

    for rank, document in enumerate(retrieved_documents, start=1):
        metadata = getattr(document, "metadata", None) or {}
        score = getattr(document, "score", None)
        if score is not None:
            scores.append(float(score))
        source_id = f"source_{rank}"
        chunk_id = _metadata_value(metadata, "chunk_id", "id")
        citations.append(Citation(
            source_id=source_id,
            rank=rank,
            score=score,
            document_name=_metadata_value(metadata, "document_name", "file_name", "source"),
            page_number=_metadata_value(metadata, "page_number", "page"),
            chunk_id=str(chunk_id) if chunk_id is not None else None,
        ))
        source_chunks.append(SourceChunk(
            source_id=source_id,
            rank=rank,
            text=getattr(document, "text", ""),
            score=score,
            metadata=metadata,
        ))

    confidence = max(scores) if scores else None
    if confidence is not None:
        confidence = max(0.0, min(1.0, confidence))

    return ChatAnswerResponse(
        knowledge_base_id=str(knowledge_base_id),
        answer=answer,
        citations=citations,
        source_chunks=source_chunks,
        confidence=confidence,
        retrieval_metadata=RetrievalMetadata(
            requested_top_k=limit,
            returned_count=len(retrieved_documents),
            vector_top_k=limit,
        ),
        trace_id=trace_id,
        message=ResponseStatus.NLP_RAG_ANSWER_SUCCESS.value,
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
    
    
@nlp_router.post("/index/answer/{knowledge_base_id}", response_model=ChatAnswerResponse)
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
    answer, _, _, retrieved_documents = await nlp_controller.answer_rag_query(
        knowledge_base=knowledge_base , 
        query_text=search_request.text , 
        limit=search_request.limit
    )
    if not answer:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "knowledge_base_id": str(knowledge_base_id), 
            "trace_id": str(uuid4()),
            "message": ResponseStatus.NLP_RAG_ANSWER_ERROR.value})

    response = _build_chat_contract(
        knowledge_base_id=knowledge_base_id,
        answer=answer,
        retrieved_documents=retrieved_documents,
        limit=search_request.limit or 5,
        trace_id=str(uuid4()),
    )
    return response