from redis import Redis
from rq import Queue

from app.config import settings

redis_connection = Redis.from_url(settings.redis_url, socket_connect_timeout=5)
q = Queue("documents", connection=redis_connection, default_timeout=settings.worker_timeout)
