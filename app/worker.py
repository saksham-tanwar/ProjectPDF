"""Document worker.

Normally its own process (`python -m app.worker`), which is what the Render blueprint and docker compose run.
It can also run inside the web process (`RUN_WORKER_IN_WEB=true`) for hosts whose free tier has no background
worker: same code, same queue, one less service to pay for. See docs/DEPLOYMENT.md for the trade-offs.
"""
import logging
import os
import threading

from redis import Redis
from rq import SimpleWorker, Worker
from rq.timeouts import TimerDeathPenalty

from app.config import Settings, get_settings
from app.log_config import configure_logging
from app.queue.q import create_queue

log = logging.getLogger(__name__)


class InProcessWorker(SimpleWorker):
    """Runs jobs in the calling thread.

    Signals only reach the main thread, so handlers are skipped and timeouts use a timer instead of SIGALRM.
    This is also what Windows needs, since it has neither fork() nor SIGALRM.
    """

    death_penalty_class = TimerDeathPenalty

    def _install_signal_handlers(self) -> None:
        return None


def build_worker(settings: Settings, connection: Redis, in_thread: bool = False):
    queue = create_queue(connection, settings)
    worker_class = InProcessWorker if (in_thread or os.name == "nt") else Worker
    return worker_class([queue], connection=connection)


def create_connection(settings: Settings) -> Redis:
    return Redis.from_url(settings.redis_url, socket_connect_timeout=5, health_check_interval=30)


def start_in_thread(settings: Settings) -> threading.Thread:
    """Starts a worker beside the web server. The thread is a daemon: an interrupted job is left for the stalled-job
    check to mark failed, which is the same outcome as a worker process being killed."""
    connection = create_connection(settings)
    worker = build_worker(settings, connection, in_thread=True)

    def run() -> None:
        log.info("Worker running inside the web process on queue %s", worker.queues[0].name)
        try:
            worker.work(with_scheduler=False, logging_level=settings.log_level)
        except Exception:
            log.exception("In-process worker stopped")

    thread = threading.Thread(target=run, name="document-worker", daemon=True)
    thread.start()
    return thread


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    connection = create_connection(settings)
    worker = build_worker(settings, connection)
    log.info("Starting %s on queue %s", type(worker).__name__, worker.queues[0].name)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
