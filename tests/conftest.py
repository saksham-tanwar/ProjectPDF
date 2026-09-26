import io
import os
import re
import uuid
import zlib

os.environ.setdefault("APP_ENV", "test")

import fakeredis
import numpy as np
import pytest
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.config import Settings
from app.services import ai

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


# Words in the same group share a dimension, so "guarantee" is semantically close to "warranty"
# without the two sharing any keyword.
CONCEPTS = [
    {"warranty", "guarantee", "guaranteed", "defects", "coverage", "covered", "covers"},
    {"return", "returns", "refund", "refunds", "money", "back"},
    {"descale", "descaling", "limescale", "cleaning", "clean", "maintenance"},
]

MANUAL = make_pdf([
    "Warranty\nNorthwind covers manufacturing defects for two years from purchase.",
    "Returns\nUnused products can be sent back within thirty days for a refund.",
    "Care\nDescale the machine every eight weeks to prevent limescale.",
])


def fake_embed(texts, settings):
    vectors = np.zeros((len(texts), settings.embedding_dimensions), dtype=np.float32)
    for row, text in enumerate(texts):
        for word in re.findall(r"[a-z]+", text.lower()):
            concept = next((index for index, group in enumerate(CONCEPTS) if word in group), None)
            if concept is not None:
                vectors[row, concept] += 3.0
            else:
                vectors[row, 10 + zlib.crc32(word.encode()) % (settings.embedding_dimensions - 10)] += 0.2
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


class FakeAI:
    def __init__(self):
        self.answer_calls = []
        self.rewrite_calls = []
        self.complete_calls = []
        self.fail_answers = False
        self.fail_embeddings = False
        self.fail_completions = False

    def embed_texts(self, texts, settings):
        if self.fail_embeddings:
            raise ai.AIServiceError("boom")
        return fake_embed(texts, settings)

    def standalone_question(self, question, history, settings):
        self.rewrite_calls.append((question, history))
        return "How do refunds work?"

    def generate_answer(self, question, history, sources, settings):
        if self.fail_answers:
            raise ai.AIServiceError("boom")
        self.answer_calls.append({"question": question, "history": history, "sources": sources})
        return f"Generated answer [p. {sources[0]['page']}]"

    def complete(self, messages, settings, max_tokens, purpose):
        """Stands in for summarisation: echoes how much text it was given so tests can check map-reduce."""
        if self.fail_completions:
            raise ai.AIServiceError("boom")
        self.complete_calls.append({"purpose": purpose, "content": messages[-1]["content"], "max_tokens": max_tokens})
        if purpose == "Section summary":
            return f"[section note {len(self.complete_calls)}]"
        return (
            "This manual explains the warranty, returns and care for the Northwind machine.\n"
            "KEY POINTS:\n"
            "• Manufacturing defects are covered for two years [p. 1]\n"
            "• Unused products can be returned within thirty days [p. 2]\n"
        )


MANUAL = make_pdf([
    "Warranty\nNorthwind covers manufacturing defects for two years from purchase.",
    "Returns\nUnused products can be sent back within thirty days for a refund.",
    "Care\nDescale the machine every eight weeks to prevent limescale.",
])


@pytest.fixture
def fake_ai(monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(ai, "embed_texts", fake.embed_texts)
    monkeypatch.setattr(ai, "standalone_question", fake.standalone_question)
    monkeypatch.setattr(ai, "generate_answer", fake.generate_answer)
    monkeypatch.setattr(ai, "complete", fake.complete)
    return fake
