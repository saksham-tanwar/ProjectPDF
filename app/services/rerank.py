"""Cross-encoder reranking.

Vector and keyword search are cheap but approximate: they score a passage without ever looking at it next to the
question. A cross-encoder reads the pair together, so it is far better at ordering the final few candidates. The model
is small (~80 MB), runs locally on CPU and costs nothing per query — the trade-off is ~110 MB of memory and a few tens
of milliseconds per query. Whether it runs at all is decided by RERANK_MODE; see eval/README.md for the measurements
behind the default.
"""
import logging
import threading

from app.config import Settings

log = logging.getLogger(__name__)

_encoder = None
_load_failed = False
_lock = threading.Lock()


def get_encoder(settings: Settings):
    """Loads the model once per process. A failure disables reranking instead of breaking search."""
    global _encoder, _load_failed
    if _encoder is not None or _load_failed:
        return _encoder
    with _lock:
        if _encoder is None and not _load_failed:
            try:
                from fastembed.rerank.cross_encoder import TextCrossEncoder

                settings.model_cache_dir.mkdir(parents=True, exist_ok=True)
                _encoder = TextCrossEncoder(
                    model_name=settings.reranker_model,
                    cache_dir=str(settings.model_cache_dir),
                    threads=settings.reranker_threads,
                )
                log.info("Reranker %s ready", settings.reranker_model)
            except Exception:
                _load_failed = True
                log.exception("Reranker unavailable; continuing with fused retrieval order")
    return _encoder


def reset_for_tests() -> None:
    global _encoder, _load_failed
    _encoder, _load_failed = None, False


def rerank(query: str, passages: list[dict], settings: Settings, limit: int) -> list[dict]:
    """Returns the best `limit` passages, ordered by cross-encoder score. Falls back to the given order."""
    if len(passages) <= 1:
        return passages[:limit]
    encoder = get_encoder(settings)
    if encoder is None:
        return passages[:limit]
    # The model reads at most ~512 tokens, so feeding it more text costs time without changing the score.
    documents = [passage["text"][: settings.rerank_max_chars] for passage in passages]
    try:
        scores = list(encoder.rerank(query, documents))
    except Exception:
        log.exception("Reranking failed; keeping fused retrieval order")
        return passages[:limit]
    ranked = sorted(zip(scores, passages), key=lambda pair: pair[0], reverse=True)
    return [{**passage, "score": float(score)} for score, passage in ranked[:limit]]
