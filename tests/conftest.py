import io
import os
import uuid

os.environ.setdefault("APP_ENV", "test")

import fakeredis
import pytest
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.config import Settings

TEST_MONGO_URL = os.environ.get("TEST_MONGO_URL", "mongodb://localhost:27017")


def make_pdf(pages: list[str]) -> bytes:
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for text in pages:
        y = 800
        for line in text.split("\n"):
            pdf.drawString(50, y, line)
            y -= 16
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


@pytest.fixture(scope="session")
def mongo_available() -> bool:
    try:
        client = MongoClient(TEST_MONGO_URL, serverSelectionTimeoutMS=1_000)
        client.admin.command("ping")
        client.close()
        return True
    except PyMongoError:
        return False


@pytest.fixture
def settings_overrides() -> dict:
    """Override in a test module to change settings for every test there."""
    return {}


@pytest.fixture
def settings(tmp_path, settings_overrides) -> Settings:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root></div>")
    (dist / "assets" / "app.js").write_text("console.log('ok')")
    return Settings(
        app_env="test",
        public_base_url="http://testserver",
        mongo_url=TEST_MONGO_URL,
        mongo_database=f"paperchat_test_{uuid.uuid4().hex[:10]}",
        upload_dir=tmp_path / "uploads",
        frontend_dist_dir=dist,
        dev_login_enabled=True,
        max_upload_mb=1,
        rate_limit_questions_per_minute=5,
        _env_file=None,
        **settings_overrides,
    )


@pytest.fixture
def client(settings, mongo_available, monkeypatch):
    if not mongo_available:
        pytest.skip(f"MongoDB is not reachable at {TEST_MONGO_URL}")
    from fastapi.testclient import TestClient
    from rq import Queue

    from app.queue import workers
    from app.server import create_app
    from app.services.storage import LocalStorage

    # Jobs run inline (is_async=False) and must see the same settings as the app.
    monkeypatch.setattr(workers, "get_settings", lambda: settings)
    server = fakeredis.FakeServer()
    queue = Queue("documents", connection=fakeredis.FakeRedis(server=server), is_async=False)
    app = create_app(
        settings,
        queue=queue,
        redis=fakeredis.FakeAsyncRedis(server=server),
        storage=LocalStorage(settings.upload_dir),
    )
    with TestClient(app) as test_client:
        yield test_client
    mongo = MongoClient(settings.mongo_url)
    mongo.drop_database(settings.mongo_database)
    mongo.close()
