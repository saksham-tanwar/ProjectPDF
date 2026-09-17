"""Synchronous RQ worker: extraction deliberately runs outside the web process."""
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient

from app.config import settings


def split_text(text: str, size: int = 1_200, overlap: int = 180) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    result, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        result.append(text[start:end])
        start = max(end - overlap, start + 1)
    return result


def process_file(file_id: str) -> None:
    import pdfplumber

    client = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=10_000)
    database = client[settings.mongo_database]
    files, chunks, oid = database.files, database.chunks, ObjectId(file_id)
    try:
        chunks.create_index("file_id")
        document = files.find_one({"_id": oid})
        if not document:
            return
        files.update_one({"_id": oid}, {"$set": {"status": "processing", "error": None}})
        rows = []
        with pdfplumber.open(Path(document["file_path"])) as pdf:
            page_count = len(pdf.pages)
            for page_number, page in enumerate(pdf.pages, start=1):
                for chunk_index, text in enumerate(split_text(page.extract_text() or "")):
                    rows.append({"file_id": oid, "page": page_number, "index": chunk_index, "text": text})
        if not rows:
            raise ValueError("No selectable text was found. Scanned PDFs are not supported yet.")
        chunks.delete_many({"file_id": oid})
        chunks.insert_many(rows)
        files.update_one({"_id": oid}, {"$set": {"status": "ready", "pages": page_count, "chunk_count": len(rows), "processed_at": datetime.now(timezone.utc)}})
    except Exception as exc:
        files.update_one({"_id": oid}, {"$set": {"status": "failed", "error": str(exc)[:500]}})
        raise
    finally:
        client.close()
