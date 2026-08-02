
import logging
from collections.abc import AsyncIterator, Iterator
from typing import Final
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import iterate_in_threadpool
from tqdm.auto import tqdm

from controllers import NLPController
from helpers.config import Settings, get_settings
from models import ResponseStatus
from models.AnswerFeedbackDataModel import (
    AnswerFeedbackDataModel,
    AnswerFeedbackSubmission,
)
from models.ChunksDataModel import ChunkDataModel
from models.KnowledgeBaseDataModel import KnowledgeBaseDataModel
from routes.schemes.nlp import (
    AnswerStreamDoneEvent,
    AnswerStreamDonePayload,
    AnswerStreamErrorEvent,
    AnswerStreamErrorPayload,
    AnswerStreamFinalEvent,
    AnswerStreamFinalPayload,
    AnswerStreamTokenEvent,
    AnswerStreamTokenPayload,
    ChatAnswerResponse,
    FeedbackRequest,
    FeedbackResponse,
    PushRequest,
    SearchRequest,
)
from services.answer_finalization import AnswerFinalizationRequest, finalize_answer
from services.answer_finalization import (
    preprocessing_metadata as _preprocessing_metadata,
)
from services.langfuse_service import LangfuseService
from services.prompt_service import PromptService
from services.query_preprocessing import QueryPreprocessingSelection
from stores.llm.LLMInterface import LLMStreamingError, LLMStreamingUnsupportedError
from tasks.data_indexing import index_data_content

logger = logging.getLogger("uvicorn.error")
STREAM_ERROR_MESSAGE: Final = "Answer generation failed."
FEEDBACK_SUCCESS_MESSAGE: Final = "Feedback saved."
nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v1" , "NLP"],
)


def _generation_failure_response(knowledge_base_id: UUID) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={
            "status": False,
            "knowledge_base_id": str(knowledge_base_id),
            "detail": ResponseStatus.NLP_RAG_ANSWER_ERROR.value,
            "message": ResponseStatus.NLP_RAG_ANSWER_ERROR.value,
        },
    )


def _preprocessing_selection(search_request: SearchRequest) -> QueryPreprocessingSelection | None:
    if search_request.preprocessing is None:
        return None
    return QueryPreprocessingSelection(
        expand=search_request.preprocessing.expand,
        decompose=search_request.preprocessing.decompose,
        max_generated_queries=search_request.preprocessing.max_generated_queries,
    )


def _sse_frame(event: AnswerStreamTokenEvent | AnswerStreamFinalEvent | AnswerStreamErrorEvent | AnswerStreamDoneEvent) -> str:
    return f"event: {event.event}\ndata: {event.data.model_dump_json()}\n\n"


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
async def get_index_info(request:Request, knowledge_base_id: UUID, app_settings: Settings = Depends(get_settings)):

    # Initialize models
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    # Get or create knowledge_base
    knowledge_base = await knowledge_base_model.get_knowledge_base_or_create(knowledge_base_id)

        # Initialize NLP Controller
    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        vector_db_client=request.app.vector_db_client,
        template_parser=request.app.template_parser,
        db_client=request.app.db_client,
        settings=app_settings,
    )

    collection_info = await nlp_controller.get_vector_db_collection_info(knowledge_base=knowledge_base)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
        "knowledge_base_id": str(knowledge_base_id), 
        "collection_info": collection_info,
        "message": ResponseStatus.NLP_INDEX_INFO_SUCCESS.value})

@nlp_router.post("/index/search/{knowledge_base_id}")
async def search_index(request:Request, knowledge_base_id: UUID, search_request: SearchRequest, app_settings: Settings = Depends(get_settings)):

        # Initialize models
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    # Get or create knowledge_base
    knowledge_base = await knowledge_base_model.get_knowledge_base_or_create(knowledge_base_id)

        # Initialize NLP Controller
    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        vector_db_client=request.app.vector_db_client,
        template_parser=request.app.template_parser,
        db_client=request.app.db_client,
        settings=app_settings,
    )
    # Implement search logic here

    retrieval_result = await nlp_controller.search_index_with_metadata(
        knowledge_base=knowledge_base,
        text=search_request.text,
        limit=search_request.limit,
        strategy=search_request.strategy,
        preprocessing=_preprocessing_selection(search_request),
    )
    results = retrieval_result.documents


    if not results:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": False, 
            "knowledge_base_id": str(knowledge_base_id), 
            "message": ResponseStatus.NLP_INDEX_SEARCH_ERROR.value})
    
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": True, 
         "knowledge_base_id": str(knowledge_base_id),
         "results": [result.dict() for result in results],
         "retrieval_metadata": {"preprocessing": _preprocessing_metadata(retrieval_result.preprocessing).model_dump()},
         "message": ResponseStatus.NLP_INDEX_SEARCH_SUCCESS.value})
    
    
@nlp_router.post("/index/answer/{knowledge_base_id}", response_model=ChatAnswerResponse)
async def answer_rag(request:Request, knowledge_base_id: UUID, search_request: SearchRequest, app_settings: Settings = Depends(get_settings)):

        # Initialize models
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    # Get or create knowledge_base
    knowledge_base = await knowledge_base_model.get_knowledge_base_or_create(knowledge_base_id)

        # Initialize tracing, prompt service, and NLP Controller
    langfuse_service = getattr(request.app, "langfuse_service", None) or LangfuseService(app_settings)
    prompt_service = getattr(request.app, "prompt_service", None) or PromptService(app_settings, langfuse_service)
    trace_id = langfuse_service.create_trace_id()

    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        vector_db_client=request.app.vector_db_client,
        template_parser=request.app.template_parser,
        db_client=request.app.db_client,
        settings=app_settings,
        prompt_service=prompt_service,
        langfuse_service=langfuse_service,
    )

    with langfuse_service.trace_answer(
        trace_id,
        input={"query": search_request.text},
        metadata={"knowledge_base_id": str(knowledge_base_id), "limit": search_request.limit, "strategy": search_request.strategy},
    ) as trace:
        answer, full_prompt, chat_history, retrieved_documents, prompt_bundle, preprocessing = await nlp_controller.answer_rag_query_with_metadata(
            knowledge_base=knowledge_base , 
            query_text=search_request.text , 
            limit=search_request.limit,
            strategy=search_request.strategy,
            preprocessing=_preprocessing_selection(search_request),
        )

        response = finalize_answer(AnswerFinalizationRequest(
            knowledge_base_id=knowledge_base_id,
            query_text=search_request.text,
            raw_answer=answer,
            full_prompt=full_prompt,
            chat_history=chat_history,
            retrieved_documents=retrieved_documents,
            limit=search_request.limit or 5,
            trace_id=trace_id,
            prompt_bundle=prompt_bundle,
            preprocessing=preprocessing,
            require_citations=app_settings.REQUIRE_ANSWER_CITATIONS,
            strict_citation_validation=app_settings.STRICT_CITATION_VALIDATION,
            trace=trace,
        ))
        if response is None:
            logger.error("RAG answer generation returned no content for knowledge base %s", knowledge_base_id)
            return _generation_failure_response(knowledge_base_id)
    return response


@nlp_router.post("/index/answer/{knowledge_base_id}/feedback", response_model=FeedbackResponse)
async def submit_answer_feedback(
    request: Request,
    knowledge_base_id: UUID,
    feedback_request: FeedbackRequest,
    app_settings: Settings = Depends(get_settings),
) -> FeedbackResponse:
    if feedback_request.knowledge_base_id != str(knowledge_base_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="knowledge_base_id must match the request path",
        )

    submission = AnswerFeedbackSubmission(
        trace_id=feedback_request.trace_id,
        knowledge_base_id=knowledge_base_id,
        rating=feedback_request.rating,
        comment=feedback_request.comment,
        question=feedback_request.question,
        answer=feedback_request.answer,
        citations=[citation.model_dump(mode="json") for citation in feedback_request.citations],
        source_chunks=[source_chunk.model_dump(mode="json") for source_chunk in feedback_request.source_chunks],
    )
    async with request.app.db_client() as session:
        await session.run_sync(
            lambda sync_session: AnswerFeedbackDataModel(sync_session).upsert(submission)
        )

    langfuse_service = getattr(request.app, "langfuse_service", None) or LangfuseService(app_settings)
    langfuse_status = langfuse_service.score_feedback(
        trace_id=submission.trace_id,
        rating=submission.rating,
        comment=submission.comment,
        metadata={"knowledge_base_id": str(knowledge_base_id), "surface": "answer"},
    )
    return FeedbackResponse(
        trace_id=submission.trace_id,
        rating=submission.rating,
        comment=submission.comment,
        langfuse_status=langfuse_status,
        message=FEEDBACK_SUCCESS_MESSAGE,
    )


@nlp_router.post("/index/answer/{knowledge_base_id}/stream", response_class=StreamingResponse)
async def answer_rag_stream(request:Request, knowledge_base_id: UUID, search_request: SearchRequest, app_settings: Settings = Depends(get_settings)):
    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=request.app.db_client)
    knowledge_base = await knowledge_base_model.get_knowledge_base_or_create(knowledge_base_id)
    langfuse_service = getattr(request.app, "langfuse_service", None) or LangfuseService(app_settings)
    prompt_service = getattr(request.app, "prompt_service", None) or PromptService(app_settings, langfuse_service)
    trace_id = langfuse_service.create_trace_id()
    nlp_controller = NLPController(
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        vector_db_client=request.app.vector_db_client,
        template_parser=request.app.template_parser,
        db_client=request.app.db_client,
        settings=app_settings,
        prompt_service=prompt_service,
        langfuse_service=langfuse_service,
    )

    async def stream_events() -> AsyncIterator[str]:
        provider_iterator: Iterator[str] | None = None

        async def terminal_error(detail: str, *, log_failure: bool = True) -> AsyncIterator[str]:
            if await request.is_disconnected():
                return
            if log_failure:
                logger.error("RAG answer stream failed detail=%s knowledge_base_id=%s trace_id=%s", detail, knowledge_base_id, trace_id)
            yield _sse_frame(AnswerStreamErrorEvent(
                event="error",
                data=AnswerStreamErrorPayload(detail=detail, message=STREAM_ERROR_MESSAGE),
            ))
            if await request.is_disconnected():
                return
            yield _sse_frame(AnswerStreamDoneEvent(event="done", data=AnswerStreamDonePayload()))

        try:
            with langfuse_service.trace_answer(
                trace_id,
                input={"query": search_request.text},
                metadata={"knowledge_base_id": str(knowledge_base_id), "limit": search_request.limit, "strategy": search_request.strategy},
            ) as trace:
                if await request.is_disconnected():
                    return
                preparation = await nlp_controller.prepare_rag_answer(
                    knowledge_base=knowledge_base,
                    query_text=search_request.text,
                    limit=search_request.limit,
                    strategy=search_request.strategy,
                    preprocessing=_preprocessing_selection(search_request),
                )
                if not preparation.retrieved_documents:
                    response = finalize_answer(AnswerFinalizationRequest(
                        knowledge_base_id=knowledge_base_id,
                        query_text=search_request.text,
                        raw_answer=None,
                        full_prompt=preparation.full_prompt,
                        chat_history=preparation.chat_history,
                        retrieved_documents=preparation.retrieved_documents,
                        limit=search_request.limit or 5,
                        trace_id=trace_id,
                        prompt_bundle=preparation.prompt_bundle,
                        preprocessing=preparation.preprocessing,
                        require_citations=app_settings.REQUIRE_ANSWER_CITATIONS,
                        strict_citation_validation=app_settings.STRICT_CITATION_VALIDATION,
                        trace=trace,
                    ))
                    if response is None:
                        async for frame in terminal_error("generation_error"):
                            yield frame
                        return
                elif preparation.full_prompt is None or preparation.chat_history is None or preparation.prompt_bundle is None:
                    async for frame in terminal_error("prompt_error"):
                        yield frame
                    return
                else:
                    raw_tokens: list[str] = []
                    provider_iterator = request.app.generation_client.generate_text_stream(
                        prompt=preparation.full_prompt,
                        chat_history=preparation.chat_history,
                    )
                    async for token in iterate_in_threadpool(provider_iterator):
                        if await request.is_disconnected():
                            return
                        if not isinstance(token, str) or not token:
                            async for frame in terminal_error("invalid_token"):
                                yield frame
                            return
                        raw_tokens.append(token)
                        yield _sse_frame(AnswerStreamTokenEvent(
                            event="token",
                            data=AnswerStreamTokenPayload(content=token),
                        ))
                        await anyio.sleep(0)
                    response = finalize_answer(AnswerFinalizationRequest(
                        knowledge_base_id=knowledge_base_id,
                        query_text=search_request.text,
                        raw_answer="".join(raw_tokens),
                        full_prompt=preparation.full_prompt,
                        chat_history=preparation.chat_history,
                        retrieved_documents=preparation.retrieved_documents,
                        limit=search_request.limit or 5,
                        trace_id=trace_id,
                        prompt_bundle=preparation.prompt_bundle,
                        preprocessing=preparation.preprocessing,
                        require_citations=app_settings.REQUIRE_ANSWER_CITATIONS,
                        strict_citation_validation=app_settings.STRICT_CITATION_VALIDATION,
                        trace=trace,
                    ))
                    if response is None:
                        async for frame in terminal_error("generation_error"):
                            yield frame
                        return
                if await request.is_disconnected():
                    return
                yield _sse_frame(AnswerStreamFinalEvent(event="final", data=AnswerStreamFinalPayload(response=response)))
                if await request.is_disconnected():
                    return
                yield _sse_frame(AnswerStreamDoneEvent(event="done", data=AnswerStreamDonePayload()))
        except LLMStreamingUnsupportedError:
            async for frame in terminal_error("streaming_unsupported"):
                yield frame
        except LLMStreamingError:
            async for frame in terminal_error("provider_error"):
                yield frame
        except Exception:  # noqa: BLE001
            logger.exception("RAG answer stream internal failure knowledge_base_id=%s trace_id=%s", knowledge_base_id, trace_id)
            async for frame in terminal_error("internal_error", log_failure=False):
                yield frame
        finally:
            if provider_iterator is not None:
                close = getattr(provider_iterator, "close", None)
                if callable(close):
                    with anyio.CancelScope(shield=True):
                        await anyio.to_thread.run_sync(close)

    return StreamingResponse(stream_events(), media_type="text/event-stream")
