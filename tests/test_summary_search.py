"""Summary generation and in-document search."""
import pytest

from app.services.summarize import batch_chunks, parse_key_points, summarize_document
from tests.conftest import MANUAL


@pytest.fixture
def settings_overrides():
    return {"ai_api_key": "sk-test", "embedding_dimensions": 256}


def ready_document(client) -> dict:
    assert client.post("/auth/dev-login").status_code == 204
    document_id = client.post("/api/documents", files={"file": ("manual.pdf", MANUAL, "application/pdf")}).json()["id"]
    document = client.get(f"/api/documents/{document_id}").json()
    assert document["status"] == "ready", document
    return document


def test_batch_chunks_groups_consecutive_pages_with_page_labels():
    chunks = [{"page": page, "text": "word " * 400} for page in range(1, 11)]
    batches = batch_chunks(chunks, batch_chars=6_000)
    assert len(batches) == 4
    assert batches[0].startswith("[pages 1-3]")
    assert batches[-1].startswith("[pages 10-10]")
    assert all(len(batch) < 8_000 for batch in batches)


def test_parse_key_points_handles_a_missing_header():
    overview, points = parse_key_points("An overview.\nKEY POINTS:\n• First [p. 1]\n• Second [p. 2]")
    assert overview == "An overview."
    assert points == ["First [p. 1]", "Second [p. 2]"]

    overview, points = parse_key_points("Just an overview.\n- Loose bullet\n")
    assert overview == "Just an overview."
    assert points == ["Loose bullet"]

    assert parse_key_points("Only prose.") == ("Only prose.", [])


def test_long_documents_are_summarised_in_rounds_with_a_full_token_budget(settings, fake_ai):
    """Above the single-pass limit, sections are condensed first. Their budget must be the configured one:
    a small cap gets eaten by reasoning tokens and truncates notes mid-sentence."""
    chunks = [{"page": page, "text": "word " * 240} for page in range(1, 131)]
    result = summarize_document(chunks, settings)

    purposes = [call["purpose"] for call in fake_ai.complete_calls]
    assert purposes.count("Section summary") > 1
    assert purposes[-1] == "Document summary"
    assert {call["max_tokens"] for call in fake_ai.complete_calls} == {settings.ai_max_output_tokens}
    assert result["key_points"]


def test_single_pass_keeps_every_page_marker(settings, fake_ai):
    summarize_document([{"page": page, "text": f"Page {page} content"} for page in range(1, 6)], settings)
    sent = fake_ai.complete_calls[-1]["content"]
    assert fake_ai.complete_calls[-1]["purpose"] == "Document summary"
    assert all(f"[p. {page}]" in sent for page in range(1, 6))


def test_upload_produces_a_summary_with_key_points(client, fake_ai):
    document = ready_document(client)
    assert document["summary"].startswith("This manual explains")
    assert len(document["key_points"]) == 2
    assert document["summary_error"] is None
    assert [call["purpose"] for call in fake_ai.complete_calls] == ["Document summary"]


def test_a_failed_summary_still_leaves_the_document_usable(client, fake_ai):
    fake_ai.fail_completions = True
    document = ready_document(client)
    assert document["status"] == "ready"
    assert document["summary"] is None
    assert document["summary_error"]
    assert client.get(f"/api/documents/{document['id']}/search?q=warranty").status_code == 200


def test_summary_can_be_regenerated(client, fake_ai):
    document = ready_document(client)
    fake_ai.complete_calls.clear()
    response = client.post(f"/api/documents/{document['id']}/summary")
    assert response.status_code == 200
    assert response.json()["key_points"]
    assert fake_ai.complete_calls
    assert client.get(f"/api/documents/{document['id']}").json()["summary"].startswith("This manual explains")


def test_search_returns_ranked_passages_without_generating_an_answer(client, fake_ai):
    document = ready_document(client)
    fake_ai.answer_calls.clear()
    body = client.get(f"/api/documents/{document['id']}/search", params={"q": "how do I send it back"}).json()
    assert body["query"] == "how do I send it back"
    assert body["results"][0]["page"] == 2
    assert "thirty days" in body["results"][0]["text"]
    assert fake_ai.answer_calls == []


def test_search_is_validated_and_private_to_the_owner(client, fake_ai):
    document = ready_document(client)
    assert client.get(f"/api/documents/{document['id']}/search?q=").status_code == 422
    client.post("/auth/logout")
    assert client.get(f"/api/documents/{document['id']}/search?q=warranty").status_code == 401
