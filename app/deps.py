"""FastAPI dependencies. Shared resources live on app.state and are created in the lifespan handler."""
from fastapi import HTTPException, Request
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from rq import Queue

from app.config import Settings
from app.services.auth import session_token, user_for_token
from app.services.storage import Storage


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> AsyncDatabase:
    return request.app.state.db


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_queue(request: Request) -> Queue:
    return request.app.state.queue


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


async def current_user(request: Request) -> dict:
    user = await user_for_token(request.app.state.db, session_token(request))
    if not user:
        raise HTTPException(401, "Please sign in to continue.")
    return user
