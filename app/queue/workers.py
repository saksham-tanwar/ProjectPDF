"""RQ jobs. These run synchronously in the worker process, never in the web process."""
import logging
from datetime import datetime, timezone

from bson import ObjectId

from app.config import get_settings
from app.db.client import create_sync_client
from app.services import ai
from app.services.storage import create_storage

log = logging.getLogger(__name__)

GENERIC_FAILURE = "We couldn't process this PDF. It may be damaged or password-protected."


class UserFacingError(Exception):
    """A processing failure whose message is safe to show to the document owner."""


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
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return result


def extract_chunks(pdf_path, max_pages: int) -> tuple[int, list[dict]]:
    import pdfplumber
    from pdfminer.pdfdocument import PDFEncryptionError
    from pdfplumber.utils.exceptions import PdfminerException

    try:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            if page_count > max_pages:
                raise UserFacingError(f"This PDF has {page_count} pages; the limit is {max_pages}.")
            rows = []
            for page_number, page in enumerate(pdf.pages, start=1):
                for chunk_index, text in enumerate(split_text(page.extract_text() or "")):
                    rows.append({"page": page_number, "index": chunk_index, "text": text})
                page.close()
    except PdfminerException as error:
        if any(isinstance(arg, PDFEncryptionError) for arg in error.args):
            raise UserFacingError("This PDF is password-protected.")
        raise
    if not rows:
        raise UserFacingError("No selectable text was found. Scanned PDFs are not supported yet.")
    return page_count, rows


def _mark_failed(file_id: str, message: str) -> None:
    settings = get_settings()
    client = create_sync_client(settings)
    try:
        client[settings.mongo_database].files.update_one(
            {"_id": ObjectId(file_id), "status": {"$ne": "ready"}},
            {"$set": {"status": "failed", "error": message, "updated_at": datetime.now(timezone.utc)}},
        )
    finally:
        client.close()


def process_file(file_id: str) -> None:
    settings = get_settings()
    client = create_sync_client(settings)
    database = client[settings.mongo_database]
    oid = ObjectId(file_id)
    try:
        document = database.files.find_one({"_id": oid})
        if not document:
            log.info("Document %s was deleted before processing", file_id)
            return
        database.files.update_one(
            {"_id": oid}, {"$set": {"status": "processing", "error": None, "updated_at": datetime.now(timezone.utc)}}
        )
        with create_storage(settings).local_copy(document["storage_key"]) as path:
            page_count, rows = extract_chunks(path, settings.max_pages)
        embedding_signature = None
        if settings.ai_enabled:
            try:
                vectors = ai.embed_texts([row["text"] for row in rows], settings)
            except ai.AIServiceError:
                log.exception("Embedding failed for document %s", file_id)
                raise UserFacingError("We couldn't prepare this PDF for AI answers. Please delete it and upload it again.")
            for row, vector in zip(rows, vectors):
                row["embedding"] = ai.to_bson_vector(vector)
            embedding_signature = ai.embedding_signature(settings)
        for row in rows:
            row.update(file_id=oid, owner_id=document["owner_id"])
        database.chunks.delete_many({"file_id": oid})
        database.chunks.insert_many(rows, ordered=False)
        result = database.files.update_one(
            {"_id": oid},
            {"$set": {
                "status": "ready",
                "pages": page_count,
                "chunk_count": len(rows),
                "embedding_signature": embedding_signature,
                "processed_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        if result.matched_count == 0:
            # Deleted while processing: don't leave orphaned chunks behind.
            database.chunks.delete_many({"file_id": oid})
    except UserFacingError as error:
        _mark_failed(file_id, str(error))
    except Exception:
        log.exception("Processing failed for document %s", file_id)
        _mark_failed(file_id, GENERIC_FAILURE)
        raise
    finally:
        client.close()


def on_job_failure(job, connection, exc_type, exc_value, traceback) -> None:
    """Covers failures that bypass process_file's own handling, such as job timeouts."""
    if exc_type is not None and issubclass(exc_type, Exception) and job.args:
        message = "Processing took too long. Try a smaller PDF." if "Timeout" in exc_type.__name__ else GENERIC_FAILURE
        _mark_failed(job.args[0], message)
