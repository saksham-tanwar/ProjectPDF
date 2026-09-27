"""Worker entry point: `python -m app.worker`. Reads REDIS_URL from settings instead of CLI flags."""
import logging
import os

from redis import Redis
from rq import SimpleWorker, Worker
from rq.timeouts import TimerDeathPenalty

from app.config import get_settings
from app.log_config import configure_logging
from app.queue.q import create_queue


class WindowsWorker(SimpleWorker):
    # Windows has no fork() or SIGALRM, so run jobs in-process with a timer-based timeout. Development only.
    death_penalty_class = TimerDeathPenalty


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    connection = Redis.from_url(settings.redis_url, socket_connect_timeout=5, health_check_interval=30)
    queue = create_queue(connection, settings)
    worker_class = WindowsWorker if os.name == "nt" else Worker
    logging.getLogger(__name__).info("Starting %s on queue %s", worker_class.__name__, queue.name)
    worker_class([queue], connection=connection).work(with_scheduler=False)


if __name__ == "__main__":
    main()
