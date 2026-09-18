import asyncio

from pymongo import AsyncMongoClient

from app.services.auth import SESSION_COOKIE, create_session, upsert_user
from tests.conftest import make_pdf

MANUAL = make_pdf([
    "Paperchat user manual\nThe warranty covers manufacturing defects for two years.",
    "Returns\nCustomers may return unused products within thirty days for a refund.",
])


def login(client):
    response = client.post("/auth/dev-login")
    assert response.status_code == 204
    return response


def upload(client, content=MANUAL, name="manual.pdf", content_type="application/pdf"):
    return client.post("/api/documents", files={"file": (name, content, content_type)})


def session_for_other_user(settings) -> str:
    async def make():
        mongo = AsyncMongoClient(settings.mongo_url, tz_aware=True)
        db = mongo[settings.mongo_database]
        user = await upsert_user(db, provider="google", provider_id="other", email="other@example.com", name="Other", picture=None)
        token = await create_session(db, user["_id"], settings)
        await mongo.close()
        return token

    return asyncio.run(make())


def test_api_requires_sign_in(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/documents").status_code == 401
    assert upload(client).status_code == 401


def test_public_config_and_health(client):
    config = client.get("/api/config").json()
    assert config == {
        "max_upload_mb": 1,
        "max_pages": 500,
        "google_enabled": False,
        "dev_login_enabled": True,
        "ai_enabled": False,
        "ai_provider": None,
    }
    assert client.get("/healthz").json() == {"status": "ok"}


def test_session_cookie_is_http_only_and_logout_revokes_it(client):
    response = login(client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/api/me").json()["email"] == "developer@localhost"
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/api/me").status_code == 401


def test_upload_process_ask_and_delete(client, settings):
    login(client)
    response = upload(client)
    assert response.status_code == 202, response.text
    document_id = response.json()["id"]

    document = client.get(f"/api/documents/{document_id}").json()
    assert document["status"] == "ready", document
    assert document["pages"] == 2
    assert "storage_key" not in document and "owner_id" not in document
    assert [item["id"] for item in client.get("/api/documents").json()["documents"]] == [document_id]

    answer = client.post(f"/api/documents/{document_id}/questions", json={"question": "How long is the warranty?"}).json()
    assert answer["mode"] == "extractive"
    assert answer["sources"][0]["page"] == 1
    assert "warranty" in answer["sources"][0]["text"].lower()

    nothing = client.post(f"/api/documents/{document_id}/questions", json={"question": "zeppelin"}).json()
    assert nothing["mode"] == "none" and nothing["sources"] == []

    assert client.delete(f"/api/documents/{document_id}").status_code == 204
    assert client.get(f"/api/documents/{document_id}").status_code == 404
    assert not any(settings.upload_dir.rglob("*.pdf"))


def test_documents_are_private_to_their_owner(client, settings):
    login(client)
    document_id = upload(client).json()["id"]
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, session_for_other_user(settings))
    assert client.get(f"/api/documents/{document_id}").status_code == 404
    assert client.post(f"/api/documents/{document_id}/questions", json={"question": "warranty"}).status_code == 404
    assert client.delete(f"/api/documents/{document_id}").status_code == 404
    assert client.get("/api/documents").json()["documents"] == []


def test_upload_rejects_non_pdf_and_oversized_files(client):
    login(client)
    assert upload(client, b"hello", name="notes.txt", content_type="text/plain").status_code == 415
    assert upload(client, b"not really a pdf", name="fake.pdf").status_code == 415
    too_big = upload(client, b"%PDF-" + b"0" * (1024 * 1024 + 100_000))
    assert too_big.status_code == 413
    assert "1 MB" in too_big.json()["detail"]


def test_failed_extraction_is_reported_to_the_user(client):
    login(client)
    document_id = upload(client, make_pdf([""]), name="scan.pdf").json()["id"]
    document = client.get(f"/api/documents/{document_id}").json()
    assert document["status"] == "failed"
    assert "Scanned PDFs" in document["error"]
    assert client.post(f"/api/documents/{document_id}/questions", json={"question": "anything"}).status_code == 409


def test_questions_are_rate_limited(client):
    login(client)
    document_id = upload(client).json()["id"]
    statuses = [
        client.post(f"/api/documents/{document_id}/questions", json={"question": "warranty"}).status_code
        for _ in range(6)
    ]
    assert statuses[:5] == [200] * 5
    assert statuses[5] == 429


def test_cross_site_writes_are_blocked(client):
    login(client)
    response = client.post("/auth/logout", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert client.get("/api/me").status_code == 200
    assert client.post("/auth/logout", headers={"Origin": "http://testserver"}).status_code == 204


def test_delete_account_removes_everything(client):
    login(client)
    upload(client)
    assert client.delete("/api/me").status_code == 204
    assert client.get("/api/me").status_code == 401
    login(client)
    assert client.get("/api/documents").json()["documents"] == []


def test_frontend_routes_and_security_headers(client):
    page = client.get("/documents/abc")
    assert page.status_code == 200 and "root" in page.text
    assert "default-src 'self'" in page.headers["content-security-policy"]
    assert page.headers["x-frame-options"] == "DENY"
    assert client.get("/assets/app.js").headers["cache-control"].startswith("public")
    missing_api = client.get("/api/unknown")
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")
