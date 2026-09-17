"""HTTP API and single-page document workspace."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import settings
from app.db.collections.files import chunks_collection, files_collection
from app.db.client import mongo_client
from app.queue.q import q
from app.queue.workers import process_file
from app.services.answering import answer_question, retrieve_chunks
from app.utils.file import save_upload


def object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(404, "Document not found")
    return ObjectId(value)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Paperchat", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"])
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    return response


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


async def require_database() -> None:
    try:
        await mongo_client.admin.command("ping")
    except Exception:
        raise HTTPException(503, "Document storage is unavailable. Start MongoDB and try again.")


@app.get("/healthz")
async def healthcheck():
    return {"status": "healthy"}


@app.get("/")
async def workspace():
    return FileResponse(
        Path(__file__).parent / "static" / "index.html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/documents/{file_id}")
async def get_document(file_id: str):
    await require_database()
    document = await files_collection.find_one({"_id": object_id(file_id)}, {"file_path": 0})
    if not document:
        raise HTTPException(404, "Document not found")
    document["id"] = str(document.pop("_id"))
    return document


@app.post("/api/documents", status_code=202)
async def upload_document(file: UploadFile = File(...)):
    await require_database()
    name = Path(file.filename or "document.pdf").name
    if not name.lower().endswith(".pdf"):
        raise HTTPException(415, "Only PDF files are supported")
    if file.content_type and file.content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(415, "The uploaded file is not a PDF")
    inserted = await files_collection.insert_one({"name": name, "status": "uploading", "created_at": datetime.now(timezone.utc)})
    file_path = settings.upload_dir / f"{inserted.inserted_id}.pdf"
    try:
        size = await save_upload(file, file_path, settings.max_upload_bytes)
        await files_collection.update_one({"_id": inserted.inserted_id}, {"$set": {"status": "queued", "file_path": str(file_path), "size": size}})
        q.enqueue(process_file, str(inserted.inserted_id), job_timeout=settings.worker_timeout)
    except HTTPException:
        await files_collection.delete_one({"_id": inserted.inserted_id})
        file_path.unlink(missing_ok=True)
        raise
    except Exception:
        await files_collection.update_one({"_id": inserted.inserted_id}, {"$set": {"status": "failed", "error": "Upload could not be queued"}})
        raise HTTPException(500, "Unable to queue document processing")
    return {"id": str(inserted.inserted_id), "status": "queued"}


@app.post("/api/documents/{file_id}/questions")
async def question_document(file_id: str, payload: Question):
    await require_database()
    oid = object_id(file_id)
    document = await files_collection.find_one({"_id": oid})
    if not document:
        raise HTTPException(404, "Document not found")
    if document["status"] != "ready":
        raise HTTPException(409, "This document is not ready yet")
    chunks = await retrieve_chunks(chunks_collection, oid, payload.question)
    if not chunks:
        return {"answer": "I couldn't find relevant text in this PDF.", "sources": [], "mode": "extractive"}
    answer, mode = await asyncio.to_thread(answer_question, payload.question, chunks)
    return {"answer": answer, "sources": chunks, "mode": mode}


@app.delete("/api/documents/{file_id}", status_code=204)
async def delete_document(file_id: str):
    await require_database()
    oid = object_id(file_id)
    document = await files_collection.find_one({"_id": oid})
    if not document:
        raise HTTPException(404, "Document not found")
    await files_collection.delete_one({"_id": oid})
    await chunks_collection.delete_many({"file_id": oid})
    if document.get("file_path"):
        Path(document["file_path"]).unlink(missing_ok=True)
