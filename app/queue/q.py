from redis import Redis
from rq import Callback, Queue

from app.config import Settings

QUEUE_NAME = "documents"


def create_queue(connection: Redis, settings: Settings, is_async: bool = True) -> Queue:
    return Queue(QUEUE_NAME, connection=connection, default_timeout=settings.worker_timeout_seconds, is_async=is_async)


def enqueue_processing(queue: Queue, file_id: str, settings: Settings) -> None:
    from app.queue.workers import on_job_failure, process_file

    queue.enqueue(
        process_file,
        file_id,
        job_id=f"process-{file_id}",
        job_timeout=settings.worker_timeout_seconds,
        on_failure=Callback(on_job_failure),
        result_ttl=3_600,
        failure_ttl=7 * 86_400,
    )
