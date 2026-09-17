from pathlib import Path

from fastapi import HTTPException, UploadFile


async def save_upload(file: UploadFile, destination: Path, maximum_size: int) -> int:
    """Persist a bounded PDF upload without trusting the supplied filename."""
    total, first_chunk = 0, b""
    try:
        with destination.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                if not first_chunk:
                    first_chunk = chunk
                total += len(chunk)
                if total > maximum_size:
                    raise HTTPException(413, f"PDF must be smaller than {maximum_size // 1024 // 1024} MB")
                output.write(chunk)
    finally:
        await file.close()
    if not first_chunk.startswith(b"%PDF-"):
        destination.unlink(missing_ok=True)
        raise HTTPException(415, "The uploaded file is not a valid PDF")
    return total
