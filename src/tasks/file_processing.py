import asyncio
import logging
from uuid import UUID

from celery_app import celery_app, get_setup_utilites
from models.AssetModel import AssetModel
from models.ChunksDataModel import ChunkDataModel
from models.ProjectDataModel import ProjectDataModel
from models.db_schemes import DataChunk
from models.enums.AssetTypeEnum import AssetTypeEnum
from models.enums.ResponseEnums import ResponseStatus
from controllers import NLPController, ProcessFileController

logger = logging.getLogger("celery.task")


@celery_app.task(
    bind=True,
    name="tasks.file_processing.process_project_files",
    acks_late=True,
    reject_on_worker_lost=True,
    time_limit=3600,
    soft_time_limit=3500,
)
def process_project_files(
    self,
    project_id: UUID,
    file_id: str | None,
    chunk_size: int,
    overlap_size: int,
    do_reset: bool = False,
):
    return asyncio.run(
        _process_project_files(
            task_instance=self,
            project_id=project_id,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
            do_reset=do_reset,
        )
    )


async def _process_project_files(
    task_instance,
    project_id,
    file_id,
    chunk_size,
    overlap_size,
    do_reset,
):
    db_engine = None
    vector_db_client = None

    try:
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

        project_model = await ProjectDataModel.create_instance(
            db_client=db_client
        )

        project = await project_model.get_project_or_create(project_id)

        nlp_controller = NLPController(
            vector_db_client=vector_db_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            template_parser=template_parser,
        )

        chunk_model = await ChunkDataModel.create_instance(
            db_client=db_client
        )

        asset_model = await AssetModel.create_instance(
            db_client=db_client
        )

        process_file_controller = ProcessFileController(
            project.project_id
        )

        project_files = {}

        if file_id:
            asset_record = (
                await asset_model.get_asset_by_name_and_projectid(
                    file_id,
                    project.project_id,
                )
            )

            if not asset_record:
                raise FileNotFoundError(
                    f"File '{file_id}' was not found "
                    f"in project '{project_id}'."
                )

            project_files = {
                asset_record.asset_id: asset_record.asset_name
            }

        else:
            assets = await asset_model.get_all_assets_by_project(
                project.project_id,
                AssetTypeEnum.File.value,
            )

            project_files = {
                asset.asset_id: asset.asset_name
                for asset in assets
            }

        if not project_files:
            raise FileNotFoundError(
                f"No files were found in project '{project_id}'."
            )

        if do_reset:
            collection_name = (
                await nlp_controller.create_collection_name(
                    str(project.project_id)
                )
            )

            await vector_db_client.drop_collection(collection_name)

            await chunk_model.delete_chunks_by_project(
                str(project.project_id)
            )

        inserted_chunks_count = 0
        number_of_processed_files = 0
        number_of_skipped_files = 0
        total_files = len(project_files)

        for file_number, (
            asset_id,
            asset_name,
        ) in enumerate(project_files.items(), start=1):

            logger.info(
                "Processing file '%s' with asset ID '%s' "
                "in project '%s'.",
                asset_name,
                asset_id,
                project_id,
            )

            task_instance.update_state(
                state="PROCESSING",
                meta={
                    "status": True,
                    "project_id": str(project_id),
                    "file_id": str(asset_id),
                    "filename": asset_name,
                    "current_file": file_number,
                    "total_files": total_files,
                    "processed_files": number_of_processed_files,
                    "inserted_chunks_count": inserted_chunks_count,
                    "message": (
                        f"Processing file {file_number} "
                        f"of {total_files}: {asset_name}"
                    ),
                },
            )

            file_content = (
                process_file_controller.get_document_content(
                    asset_name
                )
            )

            if not file_content:
                number_of_skipped_files += 1

                logger.error(
                    "File '%s' could not be loaded "
                    "for project '%s'.",
                    asset_name,
                    project_id,
                )

                continue

            file_chunks = process_file_controller.process_file(
                file_content,
                chunk_size,
                overlap_size,
            )

            if not file_chunks:
                number_of_skipped_files += 1

                logger.error(
                    "No chunks were generated for file '%s' "
                    "in project '%s'.",
                    asset_name,
                    project_id,
                )

                continue

            file_chunk_records = [
                DataChunk(
                    chunk_content=chunk.page_content,
                    chunk_metadata=chunk.metadata,
                    chunk_order=index + 1,
                    chunk_project_id=project.project_id,
                    chunk_asset_id=asset_id,
                )
                for index, chunk in enumerate(file_chunks)
            ]

            inserted_for_file = (
                await chunk_model.bulk_insert_data_chunks(
                    file_chunk_records
                )
            )

            if not inserted_for_file:
                raise RuntimeError(
                    f"No chunks were inserted for file "
                    f"'{asset_name}' in project '{project_id}'."
                )

            inserted_chunks_count += inserted_for_file
            number_of_processed_files += 1

        if number_of_processed_files == 0:
            raise RuntimeError(
                f"None of the files in project "
                f"'{project_id}' could be processed."
            )

        result = {
            "status": True,
            "project_id": str(project_id),
            "file_id": str(file_id) if file_id else None,
            "inserted_chunks_count": inserted_chunks_count,
            "number_of_processed_files": number_of_processed_files,
            "number_of_skipped_files": number_of_skipped_files,
            "message": ResponseStatus.FILE_PROCESSED_SUCCESS.value,
        }

        logger.info(
            "Project '%s' processing completed. "
            "Processed files: %s, skipped files: %s, "
            "inserted chunks: %s.",
            project_id,
            number_of_processed_files,
            number_of_skipped_files,
            inserted_chunks_count,
        )
        
        return result

    except Exception:
        logger.exception(
            "Error processing file '%s' in project '%s'.",
            file_id,
            project_id,
        )

        # Do not manually call update_state(state="FAILURE").
        # Raising the exception lets Celery store it correctly.
        raise

    finally:
        try:
            if db_engine is not None:
                await db_engine.dispose()

            if vector_db_client is not None:
                await vector_db_client.disconnect()

        except Exception:
            logger.exception(
                "An error occurred while cleaning up resources "
                "for project '%s'.",
                project_id,
            )