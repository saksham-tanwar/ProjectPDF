"""Users and server-side sessions. The browser only ever holds an opaque random token."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import Request, Response
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.config import Settings

SESSION_COOKIE = "paperchat_session"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def now() -> datetime:
    return datetime.now(timezone.utc)


async def upsert_user(db: AsyncDatabase, *, provider: str, provider_id: str, email: str, name: str, picture: str | None) -> dict:
    timestamp = now()
    return await db.users.find_one_and_update(
        {"provider": provider, "provider_id": provider_id},
        {
            "$set": {"email": email, "name": name, "picture": picture, "last_login_at": timestamp},
            "$setOnInsert": {"created_at": timestamp},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )


async def create_session(db: AsyncDatabase, user_id: ObjectId, settings: Settings) -> str:
    token = secrets.token_urlsafe(32)
    timestamp = now()
    await db.sessions.insert_one({
        "_id": _hash(token),
        "user_id": user_id,
        "created_at": timestamp,
        "expires_at": timestamp + timedelta(days=settings.session_ttl_days),
    })
    return token


async def user_for_token(db: AsyncDatabase, token: str | None) -> dict | None:
    if not token:
        return None
    session = await db.sessions.find_one({"_id": _hash(token), "expires_at": {"$gt": now()}})
    if not session:
        return None
    return await db.users.find_one({"_id": session["user_id"]})


async def delete_session(db: AsyncDatabase, token: str | None) -> None:
    if token:
        await db.sessions.delete_one({"_id": _hash(token)})


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_days * 86_400,
        httponly=True,
        secure=settings.public_base_url.startswith("https://"),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, secure=settings.public_base_url.startswith("https://"), samesite="lax", path="/"
    )


def session_token(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def public_user(user: dict) -> dict:
    return {"id": str(user["_id"]), "email": user["email"], "name": user["name"], "picture": user.get("picture")}
