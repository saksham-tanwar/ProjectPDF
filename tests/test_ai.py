"""Provider-layer tests: a fake OpenAI-compatible client records exactly what would be sent."""
from types import SimpleNamespace

import numpy as np
import pytest

from app.config import Settings
from app.services import ai

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def make_settings(**overrides) -> Settings:
    return Settings(app_env="test", ai_api_key="key", _env_file=None, **overrides)


class FakeClient:
    def __init__(self, native_size=3072, content="An answer [p. 1]", finish_reason="stop", index_field=True):
        self.native_size = native_size
        self.index_field = index_field  # Gemini's compatible endpoint leaves index unset
        self.content = content
        self.finish_reason = finish_reason
        self.embedding_calls = []
        self.chat_calls = []
        self.embeddings = SimpleNamespace(create=self._embed)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))

    def _embed(self, **kwargs):
        self.embedding_calls.append(kwargs)
        rng = np.random.default_rng(len(self.embedding_calls))
        data = [
            SimpleNamespace(index=index if self.index_field else None, embedding=(rng.normal(size=self.native_size) + position).tolist())
            for position, index in enumerate(range(len(kwargs["input"])))
        ]
        # OpenAI may answer out of order, which is what `index` is for; Gemini answers in order without it.
        return SimpleNamespace(data=list(reversed(data)) if self.index_field else data)

    def _chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=self.finish_reason)])


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(ai, "client_for", lambda settings, max_retries=2: client)
    return client


def test_embeddings_are_truncated_normalised_batched_and_ordered(fake_client):
    settings = make_settings(embedding_dimensions=768)
    vectors = ai.embed_texts([f"text {n}" for n in range(200)], settings)
    assert vectors.shape == (200, 768)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)
    assert [len(call["input"]) for call in fake_client.embedding_calls] == [96, 96, 8]
    assert all("dimensions" not in call for call in fake_client.embedding_calls)


def test_embeddings_keep_request_order_when_the_provider_omits_index(monkeypatch):
    """Gemini's OpenAI-compatible endpoint returns index=None; sorting on it used to crash."""
    with_index, without_index = FakeClient(), FakeClient(index_field=False)
    settings = make_settings(embedding_dimensions=768)
    monkeypatch.setattr(ai, "client_for", lambda s, max_retries=2: with_index)
    ordered = ai.embed_texts(["a", "b", "c"], settings)
    monkeypatch.setattr(ai, "client_for", lambda s, max_retries=2: without_index)
    assert np.allclose(ai.embed_texts(["a", "b", "c"], settings), ordered)


def test_embeddings_smaller_than_configured_size_are_rejected(fake_client):
    fake_client.native_size = 512
    with pytest.raises(ai.AIServiceError, match="EMBEDDING_DIMENSIONS"):
        ai.embed_texts(["x"], make_settings(embedding_dimensions=1024))


def test_provider_detection_and_token_parameter():
    openai = make_settings()
    gemini = make_settings(ai_base_url=GEMINI_URL, ai_chat_model="gemini-2.5-flash", ai_reasoning_effort="low")
    assert openai.ai_provider == "OpenAI"
    assert gemini.ai_provider == "Google Gemini"
    assert ai.chat_options(openai, 500) == {"model": "gpt-4.1-mini", "max_completion_tokens": 500}
    assert ai.chat_options(gemini, 500) == {"model": "gemini-2.5-flash", "max_tokens": 500, "reasoning_effort": "low"}


def test_answers_use_chat_completions_with_system_prompt_and_history(fake_client):
    history = [{"role": "user", "content": "Earlier question"}, {"role": "assistant", "content": "Earlier answer"}]
    answer = ai.generate_answer("What now?", history, [{"page": 3, "text": "Some text"}], make_settings())
    assert answer == "An answer [p. 1]"
    messages = fake_client.chat_calls[0]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1:3] == history
    assert "[1] (page 3)" in messages[-1]["content"] and "Question: What now?" in messages[-1]["content"]


def test_empty_completion_raises_with_finish_reason(fake_client):
    fake_client.content, fake_client.finish_reason = "", "length"
    with pytest.raises(ai.AIServiceError, match="finish_reason=length"):
        ai.generate_answer("q", [], [{"page": 1, "text": "t"}], make_settings())


def test_legacy_openai_variable_names_still_work(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-key")
    monkeypatch.setenv("OPENAI_MODEL", "legacy-model")
    settings = Settings(app_env="test", _env_file=None)
    assert settings.ai_api_key == "legacy-key"
    assert settings.ai_chat_model == "legacy-model"
