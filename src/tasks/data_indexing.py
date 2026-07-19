import asyncio
from fastapi.responses import JSONResponse
from helpers.config import get_settings, Settings
import logging
from models.ProjectDataModel import ProjectDataModel
from models.ChunksDataModel import ChunkDataModel
from models import ResponseStatus
from controllers import NLPController
from uuid import UUID
from tqdm.auto import tqdm

from celery_app import celery_app, get_setup_utilites

logger = logging.getLogger("celery.task")


@celery_app.task( bind=True, name="tasks.data_indexing.index_data_content", acks_late=True, reject_on_worker_lost=True, time_limit=3600, soft_time_limit=3500, )
def index_data_content( self, project_id: UUID, do_reset: bool = False, ):
    return asyncio.run(_index_data_content( task_instance=self, project_id=project_id, do_reset=do_reset)
)


async def _index_data_content(task_instance, project_id, do_reset, ):

    db_engine = None
    vector_db_client = None

    try:
        ( db_engine, db_client, llm_provider_factory,vectordb_provider_factory, generation_client, embedding_client, vector_db_client, template_parser ) = await get_setup_utilites()
        logger.info(f" setup_utilites completed for project_id: {project_id}")
        #start indexing
        project_model = await ProjectDataModel.create_instance(db_client=db_client)
        chunck_model = await ChunkDataModel.create_instance(db_client=db_client)

        project = await project_model.get_project_or_create(project_id)

        if not project:
            task_instance.update_state(
                state="FAILURE",
                meta={
                    "status": False,
                    "project_id": str(project_id),
                    "message": ResponseStatus.PROJECT_NOT_FOUND_ERROR.value
                }
            )
            raise Exception(
                    f"Project '{project_id}' was not found "
                )

        nlp_controller = NLPController(
            vector_db_client=vector_db_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            template_parser=template_parser
        )

        page_no = 1
        indexed_chunks_count = 0
        is_first_batch = True

        collection_name = await nlp_controller.create_collection_name(str(project.project_id))

        await vector_db_client.create_collection(
            collection_name=collection_name,
            embedding_size=embedding_client.embedd_size,
            do_reset=do_reset
        )

        total_chunks_count = await chunck_model.get_total_chunks_count_by_project(project.project_id)

        pbar = tqdm(
            total=total_chunks_count,
            desc="START: Indexing Chunks",
            position=0
        )

        try:
            while True:
                page_chunks = await chunck_model.get_data_chunks_by_project(
                    project.project_id,
                    page_no
                )

                if not page_chunks:
                    break

                chunks_ids = [chunk.chunk_id for chunk in page_chunks]

                is_indexed = await nlp_controller.index_into_vector_db(
                    project=project,
                    data_chunks=page_chunks,
                    do_reset=False,  # already reset above
                    chunk_ids=chunks_ids
                )

                if not is_indexed:
                    pbar.close()
                    task_instance.update_state(
                        state="FAILURE",
                        meta={
                            "status": False,
                            "project_id": str(project_id),
                            "indexed_chunks_count": indexed_chunks_count,
                            "message": ResponseStatus.NLP_INDEXING_ERROR.value
                        }
                    )
                    raise Exception(
                        f"Indexing failed for project '{project_id}'."
                    )

                indexed_chunks_count += len(page_chunks)
                pbar.update(len(page_chunks))

                page_no += 1
                is_first_batch = False

            pbar.close()

            # return JSONResponse(
            #     status_code=status.HTTP_200_OK,
            #     content={
            #         "status": True,
            #         "project_id": str(project_id),
            #         "indexed_chunks_count": indexed_chunks_count,
            #         "message": ResponseStatus.NLP_INDEXING_SUCCESS.value
            #     }
            # )
            task_instance.update_state(
                state="SUCCESS",
                meta={
                    "status": True,
                    "project_id": str(project_id),
                    "indexed_chunks_count": indexed_chunks_count,
                    "message": ResponseStatus.NLP_INDEXING_SUCCESS.value
                }
            )
            return {
                "status": True,
                "project_id": str(project_id),
                "indexed_chunks_count": indexed_chunks_count,
                "message": ResponseStatus.NLP_INDEXING_SUCCESS.value
            }

        except Exception as e:
            pbar.close()
            task_instance.update_state(
                state="FAILURE",
                meta={
                    "status": False,
                    "project_id": str(project_id),
                    "indexed_chunks_count": indexed_chunks_count,
                    "message": str(e)
                }
            )

        #end indexing
    except Exception:
        task_instance.update_state(
            state="FAILURE",
            meta={
                "status": False,
                "project_id": str(project_id),
                "message": ResponseStatus.NLP_INDEXING_ERROR.value
            }
        )
        logger.exception( "Error processing file '%s' in project '%s'.",  project_id, )
        # Do not manually call update_state(state="FAILURE").
        # Raising the exception lets Celery store it correctly.
    finally:
        try:
            if db_engine is not None:
                await db_engine.dispose()

            if vector_db_client is not None:
                await vector_db_client.disconnect()

        except Exception:
            logger.exception( "An error occurred while cleaning up resources " "for project '%s'.", project_id, )