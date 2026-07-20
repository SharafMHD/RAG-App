import logging
from uuid import UUID
from celery import chain
from celery_app import celery_app
from tasks.file_processing import process_knowledge_base_files
from tasks.data_indexing import index_data_content

logger = logging.getLogger("celery.task")


@celery_app.task( bind=True, name="tasks.process_workflow.process_and_index_workflow", acks_late=True, reject_on_worker_lost=True, time_limit=3600, soft_time_limit=3500, )
def process_and_index_workflow(self, knowledge_base_id: UUID, file_id: str | None, chunk_size: int, overlap_size: int, do_reset: bool = False,):
    workflow_chain = chain(
        process_knowledge_base_files.s(knowledge_base_id, file_id, chunk_size, overlap_size, do_reset),
        index_data_after_processing.s(),
    )
    result = workflow_chain.apply_async()
    return {
        "workflow_id": result.id,
        "message": "Workflow initiated successfully.",
        "tasks": [
            {
                "task_name": "process_knowledge_base_files",
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
    knowledge_base_id = previous_task_result["knowledge_base_id"]
    do_reset = previous_task_result.get("do_reset", False)
    task_result = index_data_content.apply_async(args=(knowledge_base_id, do_reset))
    return {
        "knowledge_base_id": knowledge_base_id,
        "do_reset": do_reset,
        "task_id": task_result.id,
    }
