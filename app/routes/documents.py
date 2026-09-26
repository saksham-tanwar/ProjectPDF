import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import PureWindowsPath
from typing import Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis
from rq import Queue

from app.config import Settings
from app.deps import current_user, get_db, get_queue, get_redis, get_settings, get_storage
from app.queue.q import enqueue_processing
from app.services import answering, ratelimit, summarize
from app.services.ai import AIServiceError
from app.services.auth import clear_session_cookie, public_user
from app.services.storage import Storage

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

PENDING_STATUSES = ("uploading", "queued", "processing")
PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}
STALLED_MESSAGE = "Processing didn't finish. Please delete this document and upload it again."


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4_000)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    # Recent conversation so follow-up questions ("what about the second one?") can be understood.
    history: list[Turn] = Field(default_factory=list, max_length=12)


def parse_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(404, "Document not found.")
    return ObjectId(value)


def clean_filename(filename: str | None) -> str:
    name = PureWindowsPath(filename or "").name  # Handles both / and \ separators.
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return (name or "document.pdf")[:200]


def serialize(document: dict) -> dict:
    return {
        "id": str(document["_id"]),
        "name": document["name"],
        "status": document["status"],
        "size": document.get("size"),
        "pages": document.get("pages"),
        "chunk_count": document.get("chunk_count"),
        "error": document.get("error"),
        "summary": document.get("summary"),
        "key_points": document.get("key_points") or [],
        "summary_error": document.get("summary_error"),
        "created_at": document["created_at"],
        "updated_at": document.get("updated_at"),
    }


async def fail_stalled_documents(db: AsyncDatabase, owner_id: ObjectId, settings: Settings) -> None:
    """Jobs can die without reporting back (e.g. the worker is killed); surface that instead of spinning forever."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(settings.worker_timeout_seconds * 3, 1_800))
    await db.files.update_many(
        {"owner_id": owner_id, "status": {"$in": list(PENDING_STATUSES)}, "updated_at": {"$lt": cutoff}},
        {"$set": {"status": "failed", "error": STALLED_MESSAGE, "updated_at": datetime.now(timezone.utc)}},
    )


async def owned_document(db: AsyncDatabase, file_id: str, user: dict) -> dict:
    document = await db.files.find_one({"_id": parse_id(file_id), "owner_id": user["_id"]})
    if not document:
        raise HTTPException(404, "Document not found.")
    return document


async def remove_document(db: AsyncDatabase, storage: Storage, document: dict) -> None:
    await db.files.delete_one({"_id": document["_id"]})
    await db.chunks.delete_many({"file_id": document["_id"]})
    if document.get("storage_key"):
        try:
            await run_in_threadpool(storage.delete, document["storage_key"])
        except Exception:
            log.exception("Could not delete stored object %s", document["storage_key"])


@router.get("/config")
async def public_config(settings: Settings = Depends(get_settings)):
    return {
        "max_upload_mb": settings.max_upload_mb,
        "max_pages": settings.max_pages,
        "google_enabled": settings.google_enabled,
        "dev_login_enabled": settings.dev_login_enabled and not settings.is_production,
        "ai_enabled": settings.ai_enabled,
        "ai_provider": settings.ai_provider if settings.ai_enabled else None,
    }


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return public_user(user)


@router.delete("/me", status_code=204)
async def delete_account(
    response: Response,
    user: dict = Depends(current_user),
    db: AsyncDatabase = Depends(get_db),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
):
    for document in await db.files.find({"owner_id": user["_id"]}).to_list(length=None):
        await remove_document(db, storage, document)
    await db.chunks.delete_many({"owner_id": user["_id"]})
    await db.sessions.delete_many({"user_id": user["_id"]})
    await db.users.delete_one({"_id": user["_id"]})
    clear_session_cookie(response, settings)


@router.get("/documents")
async def list_documents(
    user: dict = Depends(current_user), db: AsyncDatabase = Depends(get_db), settings: Settings = Depends(get_settings)
):
    await fail_stalled_documents(db, user["_id"], settings)
    cursor = db.files.find({"owner_id": user["_id"]}).sort("created_at", -1).limit(settings.user_max_documents)
    return {"documents": [serialize(document) for document in await cursor.to_list(length=None)]}


@router.get("/documents/{file_id}")
async def get_document(
    file_id: str,
    user: dict = Depends(current_user),
    db: AsyncDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    document = await owned_document(db, file_id, user)
    if document["status"] in PENDING_STATUSES:
        await fail_stalled_documents(db, user["_id"], settings)
        document = await owned_document(db, file_id, user)
    return serialize(document)


@router.post("/documents", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
    db: AsyncDatabase = Depends(get_db),
    redis: Redis = Depends(get_redis),
    queue: Queue = Depends(get_queue),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
):
    try:
        name = clean_filename(file.filename)
        if not name.lower().endswith(".pdf") or (file.content_type and file.content_type not in PDF_CONTENT_TYPES):
            raise HTTPException(415, "Only PDF files are supported.")
        if file.size is not None and file.size > settings.max_upload_bytes:
            raise HTTPException(413, f"The upload is too large. The limit is {settings.max_upload_mb} MB.")
        if not (await file.read(5)).startswith(b"%PDF-"):
            raise HTTPException(415, "This file isn't a valid PDF.")
        await file.seek(0)

        await ratelimit.enforce(
            redis, "uploads", str(user["_id"]), settings.rate_limit_uploads_per_hour, 3_600,
            "You've uploaded a lot of documents recently. Please try again later.",
        )
        if await db.files.count_documents({"owner_id": user["_id"]}) >= settings.user_max_documents:
            raise HTTPException(
                403, f"You can keep up to {settings.user_max_documents} documents. Delete one to upload another."
            )

        file_id = ObjectId()
        timestamp = datetime.now(timezone.utc)
        document = {
            "_id": file_id,
            "owner_id": user["_id"],
            "name": name,
            "status": "uploading",
            "size": file.size,
            "storage_key": f"documents/{user['_id']}/{file_id}.pdf",
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        await db.files.insert_one(document)
        try:
            await run_in_threadpool(storage.save, document["storage_key"], file.file)
        except Exception:
            log.exception("Storing upload %s failed", file_id)
            await db.files.delete_one({"_id": file_id})
            raise HTTPException(503, "We couldn't store your PDF. Please try again.")

        await db.files.update_one(
            {"_id": file_id}, {"$set": {"status": "queued", "updated_at": datetime.now(timezone.utc)}}
        )
        try:
            await run_in_threadpool(enqueue_processing, queue, str(file_id), settings)
        except Exception:
            log.exception("Queueing document %s failed", file_id)
            await remove_document(db, storage, document)
            raise HTTPException(503, "We couldn't start processing your PDF. Please try again.")
    finally:
        await file.close()

    stored = await db.files.find_one({"_id": file_id})
    return serialize(stored or {**document, "status": "queued"})


@router.post("/documents/{file_id}/questions")
async def ask_question(
    file_id: str,
    payload: Question,
    user: dict = Depends(current_user),
    db: AsyncDatabase = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
):
    document = await owned_document(db, file_id, user)
    if document["status"] != "ready":
        raise HTTPException(409, "This document isn't ready yet.")
    subject = str(user["_id"])
    await ratelimit.enforce(
        redis, "questions-minute", subject, settings.rate_limit_questions_per_minute, 60,
        "You're asking questions quickly. Please wait a moment and try again.",
    )
    await ratelimit.enforce(
        redis, "questions-day", subject, settings.rate_limit_questions_per_day, 86_400,
        "You've reached today's question limit. Please try again tomorrow.",
    )
    question = payload.question.strip()
    if not question:
        raise HTTPException(422, "Please enter a question.")
    history = [turn.model_dump() for turn in payload.history[-6:]]
    return await answering.answer(db.chunks, document, question, history, settings)


@router.get("/documents/{file_id}/search")
async def search_document(
    file_id: str,
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=10, ge=1, le=30),
    user: dict = Depends(current_user),
    db: AsyncDatabase = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
):
    """Passage search with no model call on the generation side: instant and free to run."""
    document = await owned_document(db, file_id, user)
    if document["status"] != "ready":
        raise HTTPException(409, "This document isn't ready yet.")
    await ratelimit.enforce(
        redis, "search", str(user["_id"]), settings.rate_limit_searches_per_minute, 60,
        "You're searching very quickly. Please wait a moment and try again.",
    )
    results = await answering.search_passages(db.chunks, document, q.strip(), settings, limit)
    return {"query": q.strip(), "results": results}


@router.post("/documents/{file_id}/summary")
async def regenerate_summary(
    file_id: str,
    user: dict = Depends(current_user),
    db: AsyncDatabase = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
):
    document = await owned_document(db, file_id, user)
    if document["status"] != "ready":
        raise HTTPException(409, "This document isn't ready yet.")
    if not settings.ai_enabled:
        raise HTTPException(503, "AI summaries aren't configured on this server.")
    await ratelimit.enforce(
        redis, "summaries", str(user["_id"]), settings.rate_limit_summaries_per_hour, 3_600,
        "You've regenerated a lot of summaries recently. Please try again later.",
    )
    chunks = await db.chunks.find(
        {"file_id": document["_id"]}, {"page": 1, "text": 1}
    ).sort([("page", 1), ("index", 1)]).to_list(length=None)
    if not chunks:
        raise HTTPException(409, "This document has no indexed text.")
    try:
        result = await run_in_threadpool(summarize.summarize_document, chunks, settings)
    except AIServiceError:
        log.exception("Summary regeneration failed for %s", file_id)
        raise HTTPException(503, "The summary service is unavailable right now. Please try again.")
    await db.files.update_one(
        {"_id": document["_id"]},
        {"$set": {**result, "summary_error": None, "summarized_at": datetime.now(timezone.utc),
                  "updated_at": datetime.now(timezone.utc)}},
    )
    return result


@router.delete("/documents/{file_id}", status_code=204)
async def delete_document(
    file_id: str,
    user: dict = Depends(current_user),
    db: AsyncDatabase = Depends(get_db),
    storage: Storage = Depends(get_storage),
):
    document = await owned_document(db, file_id, user)
    await remove_document(db, storage, document)
