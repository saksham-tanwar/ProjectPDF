import io
from pathlib import Path

import pytest
from botocore.stub import Stubber

from app.config import Settings
from app.queue.workers import UserFacingError, extract_chunks, split_text
from app.routes.documents import clean_filename
from app.services.answering import search_terms
from app.services.storage import LocalStorage, S3Storage
from tests.conftest import make_pdf


def test_split_text_bounds_chunks_and_terminates():
    chunks = split_text("alpha " * 1_000, size=100, overlap=20)
    assert len(chunks) > 10
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert chunks[-1].endswith("alpha")
    assert split_text("   ") == []


def test_clean_filename_strips_paths_and_control_characters():
    assert clean_filename(r"C:\Users\me\report.pdf") == "report.pdf"
    assert clean_filename("../../etc/pass\x00wd.pdf") == "passwd.pdf"
    assert clean_filename(None) == "document.pdf"


def test_local_storage_round_trip_and_rejects_traversal(tmp_path: Path):
    storage = LocalStorage(tmp_path)
    storage.save("documents/u/f.pdf", io.BytesIO(b"%PDF-1.4 data"))
    with storage.local_copy("documents/u/f.pdf") as path:
        assert path.read_bytes() == b"%PDF-1.4 data"
    storage.delete("documents/u/f.pdf")
    assert not (tmp_path / "documents/u/f.pdf").exists()
    with pytest.raises(ValueError):
        storage.save("../escape.pdf", io.BytesIO(b""))


def test_s3_storage_uses_bucket_and_key():
    import boto3

    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y")
    storage = S3Storage("bucket", client)
    with Stubber(client) as stub:
        stub.add_response("put_object", {}, {"Bucket": "bucket", "Key": "documents/a.pdf", "Body": b"%PDF-", "ContentType": "application/pdf"})
        stub.add_response("delete_object", {}, {"Bucket": "bucket", "Key": "documents/a.pdf"})
        storage.save("documents/a.pdf", io.BytesIO(b"%PDF-"))
        storage.delete("documents/a.pdf")
        stub.assert_no_pending_responses()


def test_extract_chunks_reads_pages_and_enforces_page_limit(tmp_path: Path):
    path = tmp_path / "doc.pdf"
    path.write_bytes(make_pdf(["The warranty lasts two years.", "Returns are accepted within 30 days."]))
    pages, rows = extract_chunks(path, max_pages=10)
    assert pages == 2
    assert {row["page"] for row in rows} == {1, 2}
    with pytest.raises(UserFacingError, match="limit is 1"):
        extract_chunks(path, max_pages=1)


def test_extract_chunks_rejects_pdf_without_text(tmp_path: Path):
    path = tmp_path / "blank.pdf"
    path.write_bytes(make_pdf([""]))
    with pytest.raises(UserFacingError, match="No selectable text"):
        extract_chunks(path, max_pages=10)


def test_production_settings_require_secure_configuration():
    with pytest.raises(ValueError) as error:
        Settings(app_env="production", public_base_url="http://example.com", dev_login_enabled=True, _env_file=None)
    message = str(error.value)
    for expected in ("https://", "SESSION_SECRET", "OPENAI_API_KEY", "GOOGLE_CLIENT_ID", "DEV_LOGIN_ENABLED", "STORAGE_BACKEND"):
        assert expected in message


def test_production_settings_accept_complete_configuration():
    settings = Settings(
        app_env="production",
        public_base_url="https://paperchat.example.com/",
        session_secret="s" * 40,
        google_client_id="id",
        google_client_secret="secret",
        openai_api_key="sk-test",
        storage_backend="s3",
        s3_bucket="bucket",
        s3_access_key_id="key",
        s3_secret_access_key="secret",
        _env_file=None,
    )
    assert settings.public_origin == "https://paperchat.example.com"
    assert settings.allowed_origins == {"https://paperchat.example.com"}


def test_search_terms_drop_phrase_and_negation_syntax():
    assert search_terms('what is "the warranty" -period?').split() == ["what", "is", "the", "warranty", "period?"]
    assert search_terms("non-refundable deposit") == "non-refundable deposit"
