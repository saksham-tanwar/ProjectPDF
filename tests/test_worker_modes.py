"""The worker can run as its own process or inside the web process; both use the same queue and job code."""
import fakeredis

from app.config import Settings
from app.worker import InProcessWorker, build_worker


def settings(**overrides) -> Settings:
    return Settings(app_env="test", _env_file=None, **overrides)


def test_in_thread_mode_uses_a_worker_that_needs_no_signals():
    worker = build_worker(settings(), fakeredis.FakeRedis(), in_thread=True)
    assert isinstance(worker, InProcessWorker)
    # Signal handlers only work on the main thread, and SIGALRM timeouts with them.
    assert worker._install_signal_handlers() is None
    assert worker.death_penalty_class.__name__ == "TimerDeathPenalty"


def test_both_modes_watch_the_same_queue():
    connection = fakeredis.FakeRedis()
    separate = build_worker(settings(), connection)
    in_web = build_worker(settings(), connection, in_thread=True)
    assert [queue.name for queue in separate.queues] == [queue.name for queue in in_web.queues] == ["documents"]
