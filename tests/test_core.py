import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.queue.workers import split_text
from app.services.answering import terms
from app.utils.file import save_upload


class Upload:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.closed = False

    async def read(self, _):
        return next(self.chunks, b"")

    async def close(self):
        self.closed = True


def test_split_text_preserves_content_and_bounds_chunks():
    text = "alpha " * 1_000
    chunks = split_text(text, size=100, overlap=20)
    assert len(chunks) > 10
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert "alpha" in chunks[0]


def test_terms_discards_short_words():
    assert terms("The PDF has a retrieval system") == {"the", "pdf", "has", "retrieval", "system"}


def test_save_upload_rejects_non_pdf(tmp_path: Path):
    target = tmp_path / "upload.pdf"
    with pytest.raises(HTTPException) as exception:
        asyncio.run(save_upload(Upload([b"not a pdf"]), target, 100))
    assert exception.value.status_code == 415
    assert not target.exists()
