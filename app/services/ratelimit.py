"""Fixed-window rate limits stored in Redis, shared by every web instance."""
import time

from fastapi import HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError


async def enforce(redis: Redis, name: str, subject: str, limit: int, window_seconds: int, message: str) -> None:
    window = int(time.time() // window_seconds)
    key = f"ratelimit:{name}:{subject}:{window}"
    try:
        async with redis.pipeline(transaction=True) as pipe:
            count, _ = await pipe.incr(key).expire(key, window_seconds + 5).execute()
    except RedisError:
        # Fail closed: these limits protect paid API usage and queue capacity.
        raise HTTPException(503, "The service is temporarily unavailable. Please try again shortly.")
    if count > limit:
        retry_after = window_seconds - int(time.time()) % window_seconds
        raise HTTPException(429, message, headers={"Retry-After": str(retry_after)})
