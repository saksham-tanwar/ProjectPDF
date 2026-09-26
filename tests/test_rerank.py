"""Cross-encoder reranking, with a fake encoder standing in for the local model."""
import re

import numpy as np
import pytest

from app.config import Settings
from app.services import rerank

PASSAGES = [
    {"page": 1, "text": "The boiler heats to 93 degrees."},
    {"page": 2, "text": "Unused products can be returned within thirty days."},
    {"page": 3, "text": "The warranty covers manufacturing defects for two years."},
]


class FakeEncoder:
    """Scores by how many query words a passage contains, so ordering is predictable."""

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def rerank(self, query, documents):
        self.calls.append({"query": query, "documents": documents})
        if self.fail:
            raise RuntimeError("model exploded")
        words = set(query.lower().split())
        return [float(len(words & set(re.findall(r"[a-z]+", document.lower())))) for document in documents]


@pytest.fixture(autouse=True)
def reset():
    rerank.reset_for_tests()
    yield
    rerank.reset_for_tests()


def settings(**overrides) -> Settings:
    return Settings(app_env="test", _env_file=None, **{"rerank_mode": "always", **overrides})


def test_rerank_reorders_by_score_and_trims_to_limit(monkeypatch):
    encoder = FakeEncoder()
    monkeypatch.setattr(rerank, "get_encoder", lambda _: encoder)
    ranked = rerank.rerank("warranty defects returned", PASSAGES, settings(), limit=2)
    assert [passage["page"] for passage in ranked] == [3, 2]
    assert ranked[0]["score"] == 2.0  # warranty + defects
    assert ranked[1]["score"] == 1.0  # returned


def test_passages_are_truncated_to_what_the_model_reads(monkeypatch):
    encoder = FakeEncoder()
    monkeypatch.setattr(rerank, "get_encoder", lambda _: encoder)
    long_passages = [{"page": 1, "text": "x" * 5_000}, {"page": 2, "text": "y" * 5_000}]
    rerank.rerank("q", long_passages, settings(rerank_max_chars=500), limit=1)
    assert [len(document) for document in encoder.calls[0]["documents"]] == [500, 500]


def test_failures_keep_the_original_order(monkeypatch):
    monkeypatch.setattr(rerank, "get_encoder", lambda _: FakeEncoder(fail=True))
    assert rerank.rerank("q", PASSAGES, settings(), limit=2) == PASSAGES[:2]

    monkeypatch.setattr(rerank, "get_encoder", lambda _: None)  # model could not be loaded
    assert rerank.rerank("q", PASSAGES, settings(), limit=2) == PASSAGES[:2]


def test_a_single_passage_needs_no_model(monkeypatch):
    monkeypatch.setattr(rerank, "get_encoder", lambda _: pytest.fail("should not load the model"))
    assert rerank.rerank("q", PASSAGES[:1], settings(), limit=2) == PASSAGES[:1]


def test_a_broken_model_is_only_attempted_once(monkeypatch):
    attempts = []

    def explode(*args, **kwargs):
        attempts.append(1)
        raise RuntimeError("no model here")

    monkeypatch.setattr("fastembed.rerank.cross_encoder.TextCrossEncoder", explode)
    config = settings()
    assert rerank.get_encoder(config) is None
    assert rerank.get_encoder(config) is None
    assert len(attempts) == 1


@pytest.mark.parametrize(
    ("mode", "has_vector", "expected"),
    [
        ("never", False, False),
        ("never", True, False),
        ("lexical-only", False, True),   # keyword-only retrieval: the cross-encoder improves it
        ("lexical-only", True, False),   # embeddings available: they rank better than the cross-encoder
        ("always", False, True),
        ("always", True, True),
    ],
)
def test_when_reranking_runs(mode, has_vector, expected):
    from app.services.answering import should_rerank

    vector = np.zeros(4) if has_vector else None
    assert should_rerank(settings(rerank_mode=mode), vector) is expected


def test_no_settings_means_no_reranking():
    from app.services.answering import should_rerank

    assert should_rerank(None, None) is False
