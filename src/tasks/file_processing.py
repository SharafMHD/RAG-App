import asyncio
import logging
from uuid import UUID

from helpers.config import get_settings
from celery_app import celery_app, get_setup_utilites
from models.AssetModel import AssetModel
from models.ChunksDataModel import ChunkDataModel
from models.KnowledgeBaseDataModel import KnowledgeBaseDataModel
from models.db_schemes import DataChunk
from models.enums.AssetTypeEnum import AssetTypeEnum
from models.enums.ResponseEnums import ResponseStatus
from controllers import NLPController, ProcessFileController
from utils.idempotencyManager import IdempotencyManager

logger = logging.getLogger("celery.task")


@celery_app.task(
    bind=True,
    name="tasks.file_processing.process_knowledge_base_files",
    acks_late=True,
    reject_on_worker_lost=True,
    time_limit=3600,
    soft_time_limit=3500,
)
def process_knowledge_base_files(
    self,
    knowledge_base_id: UUID,
    file_id: str | None,
    chunk_size: int,
    overlap_size: int,
    do_reset: bool = False,
):
    return asyncio.run(
        _process_knowledge_base_files(
            task_instance=self,
            knowledge_base_id=knowledge_base_id,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
            do_reset=do_reset,
        )
    )


async def _process_knowledge_base_files(
    task_instance, knowledge_base_id, file_id, chunk_size, overlap_size, do_reset
):
    # Setup utilities asynchronously
    (
        db_engine,
        db_client,
        llm_provider_factory,
        vectordb_provider_factory,
        generation_client,
        embedding_client,
        vector_db_client,
        template_parser,
    ) = await get_setup_utilites()

    knowledge_base_model = await KnowledgeBaseDataModel.create_instance(db_client=db_client)
    idempotency_manager = IdempotencyManager(db_client=db_client, db_engine=db_engine)

    task_args = {
        "knowledge_base_id": str(knowledge_base_id),
        "file_id": str(file_id) if file_id else None,
        "chunk_size": chunk_size,
        "overlap_size": overlap_size,
        "do_reset": do_reset,
    }
    task_name = task_instance.name
    settings = get_settings()

    # FIX: Native await used directly on async idempotency manager methods
    should_execute, existing_execution = await idempotency_manager.should_execute_task(
        celery_task_id=task_instance.request.id,
        task_name=task_name,
        task_args=task_args,
        task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    )

    if not should_execute:
        logger.warning(
            "Task '%s' with args %s has already been executed recently. Skipping.",
            task_name,
            task_args,
        )
        return existing_execution.result if existing_execution else None

    task_record = None
    try:
        celery_uuid = UUID(task_instance.request.id)
    except ValueError:
        celery_uuid = knowledge_base_id  

    if existing_execution:
        task_record = await idempotency_manager.update_task_execution_status(
            execution_id=existing_execution.execution_id,
            status="PENDING",
            result=None,
        )
    else:
        task_record = await idempotency_manager.create_task_execution_record(
            task_name=task_name,
            task_args=task_args,
            celery_task_id=celery_uuid,
        )

    # FIX: Native await transition status safely to STARTED
    await idempotency_manager.update_task_execution_status(
        execution_id=task_record.execution_id,
        status="STARTED",
        result=None,
    )

    # Master pipeline error tracking boundary
    try:
        knowledge_base = await knowledge_base_model.get_knowledge_base_or_create(knowledge_base_id)
        nlp_controller = NLPController(
            vector_db_client=vector_db_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            template_parser=template_parser,
        )

        chunk_model = await ChunkDataModel.create_instance(db_client=db_client)
        asset_model = await AssetModel.create_instance(db_client=db_client)
        process_file_controller = ProcessFileController(knowledge_base.knowledge_base_id)

        knowledge_base_files = {}

        if file_id:
            asset_record = await asset_model.get_asset_by_name_and_knowledge_baseid(
                file_id, knowledge_base.knowledge_base_id
            )
            if not asset_record:
                error_meta = {
                    "status": False,
                    "file_id": str(file_id),
                    "knowledge_base_id": str(knowledge_base_id),
                    "message": ResponseStatus.ASSET_NOT_FOUND_ERROR.value,
                }
                task_instance.update_state(state="FAILURE", meta=error_meta)
                
                await idempotency_manager.update_task_execution_status(
                    execution_id=task_record.execution_id,
                    status="FAILURE",
                    result=error_meta,
                )
                raise FileNotFoundError(
                    f"File '{file_id}' not found in knowledge_base '{knowledge_base_id}'."
                )

            knowledge_base_files = {asset_record.asset_id: asset_record.asset_name}
        else:
            assets = await asset_model.get_all_assets_by_knowledge_base(
                knowledge_base.knowledge_base_id, AssetTypeEnum.File.value
            )
            knowledge_base_files = {asset.asset_id: asset.asset_name for asset in assets}

        if not knowledge_base_files:
            raise FileNotFoundError(f"No files found in knowledge_base '{knowledge_base_id}'.")

        if do_reset:
            collection_name = await nlp_controller.create_collection_name(
                str(knowledge_base.knowledge_base_id)
            )
            await vector_db_client.drop_collection(collection_name)
            await chunk_model.delete_chunks_by_knowledge_base(str(knowledge_base.knowledge_base_id))

        inserted_chunks_count = 0
        number_of_processed_files = 0
        number_of_skipped_files = 0
        total_files = len(knowledge_base_files)

        # Sequential file operations loop
        for file_number, (asset_id, asset_name) in enumerate(
            knowledge_base_files.items(), start=1
        ):
            logger.info(
                "Processing file '%s' (ID: '%s') in knowledge_base '%s'.",
                asset_name,
                asset_id,
                knowledge_base_id,
            )

            task_instance.update_state(
                state="PROCESSING",
                meta={
                    "status": True,
                    "knowledge_base_id": str(knowledge_base_id),
                    "file_id": str(asset_id),
                    "filename": asset_name,
                    "current_file": file_number,
                    "total_files": total_files,
                    "processed_files": number_of_processed_files,
                    "inserted_chunks_count": inserted_chunks_count,
                    "message": f"Processing file {file_number} of {total_files}: {asset_name}",
                },
            )

            # Keep asyncio.to_thread here ONLY if get_document_content is completely synchronous file I/O
            file_content = await asyncio.to_thread(
                process_file_controller.get_document_content, asset_name
            )

            if not file_content:
                number_of_skipped_files += 1
                logger.warning("Skipped file '%s' due to empty content.", asset_name)
                continue

            chunks = process_file_controller.process_file(
                file_content=file_content,
                chunk_size=chunk_size,
                overlap_size=overlap_size,
            )
            if not chunks:
                number_of_skipped_files += 1
                logger.warning("Skipped file '%s' because no chunks were produced.", asset_name)
                continue

            data_chunks = [
                DataChunk(
                    chunk_asset_id=asset_id,
                    chunk_knowledge_base_id=knowledge_base.knowledge_base_id,
                    chunk_content=chunk.page_content,
                    chunk_metadata=chunk.metadata,
                    chunk_order=chunk_order,
                    chunking_strategy=(chunk.metadata or {}).get("chunking_strategy"),
                    embedding_model=(chunk.metadata or {}).get("embedding_model"),
                    content_hash=(chunk.metadata or {}).get("content_hash"),
                    parent_chunk_id=(chunk.metadata or {}).get("parent_chunk_id"),
                )
                for chunk_order, chunk in enumerate(chunks, start=1)
            ]
            inserted_chunks_count += await chunk_model.bulk_insert_data_chunks(data_chunks)
            number_of_processed_files += 1

        # Execution finished successfully
        success_meta = {
            "status": True,
            "processed_files": number_of_processed_files,
            "skipped_files": number_of_skipped_files,
            "knowledge_base_id": str(knowledge_base.knowledge_base_id),
            "do_reset": do_reset,
            "inserted_chunks": inserted_chunks_count,
        }
        await idempotency_manager.update_task_execution_status(
            execution_id=task_record.execution_id,
            status="SUCCESS",
            result=success_meta,
        )
        return success_meta

    except Exception as exc:
        logger.exception("Task processing failed dramatically.")
        if task_record:
            await idempotency_manager.update_task_execution_status(
                execution_id=task_record.execution_id,
                status="FAILURE",
                result={"error": str(exc)},
            )
        raise exc
    finally:
        try:
            if vector_db_client is not None:
                await vector_db_client.disconnect()
            if db_engine is not None:
                await db_engine.dispose()
        except Exception:
            logger.exception("An error occurred while cleaning up resources for knowledge_base '%s'.", knowledge_base_id)
