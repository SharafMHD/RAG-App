import asyncio
import logging
from uuid import UUID
from celery import chain
from celery_app import celery_app, get_setup_utilites
from tasks.file_processing import process_project_files
from tasks.data_indexing import _index_data_content

logger = logging.getLogger("celery.task")


@celery_app.task( bind=True, name="tasks.process_workflow.process_and_index_workflow", acks_late=True, reject_on_worker_lost=True, time_limit=3600, soft_time_limit=3500, )
def process_and_index_workflow(self, project_id: UUID, file_id: str | None, chunk_size: int, overlap_size: int, do_reset: bool = False,):
    workflow_chain = chain(
        process_project_files.s(project_id, file_id, chunk_size, overlap_size, do_reset),
        index_data_after_processing.s(),
    )
    result = workflow_chain.apply_async()
    return {
        "workflow_id": result.id,
        "message": "Workflow initiated successfully.",
        "tasks": [
            {
                "task_name": "process_project_files",
                "task_id": result.parent.id if result.parent else None,
            },
            {
                "task_name": "index_data_after_processing",
                "task_id": result.id,
            },
        ],
    }

@celery_app.task( bind=True, name="tasks.process_workflow.index_data_after_processing", acks_late=True, reject_on_worker_lost=True, time_limit=3600, soft_time_limit=3500, )
def index_data_after_processing(self, previous_task_result):
    task_result = asyncio.run(
        _index_data_content.apply_async(args=(previous_task_result["project_id"], previous_task_result["do_reset"])),

    )
    return {
        "project_id": previous_task_result["project_id"],
        "do_reset": previous_task_result["do_reset"],
        "task": task_result
    }