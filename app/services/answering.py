"""Retrieval-augmented answering: hybrid (semantic + keyword) retrieval, then a grounded, page-cited answer."""
import logging
import re

import numpy as np
from bson import ObjectId
from fastapi.concurrency import run_in_threadpool
from pymongo.asynchronous.collection import AsyncCollection

from app.config import Settings
from app.services import ai

log = logging.getLogger(__name__)

CANDIDATES_PER_RETRIEVER = 20
RRF_K = 60


def search_terms(question: str) -> str:
    """MongoDB $text treats quotes as phrases and a leading '-' as exclusion; users mean neither."""
    return re.sub(r'(^|\s)-+', " ", question.replace('"', " "))[:500]


def reciprocal_rank_fusion(rankings: list[list[ObjectId]], k: int = RRF_K) -> list[ObjectId]:
    """Merges ranked id lists; items ranked highly by either retriever rise to the top."""
    scores: dict[ObjectId, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda item: scores[item], reverse=True)


async def keyword_candidates(chunks: AsyncCollection, file_id: ObjectId, query: str) -> list[dict]:
    cursor = (
        chunks.find(
            {"file_id": file_id, "$text": {"$search": search_terms(query)}},
            {"page": 1, "text": 1, "score": {"$meta": "textScore"}},
        )
        .sort([("score", {"$meta": "textScore"})])
        .limit(CANDIDATES_PER_RETRIEVER)
    )
    return await cursor.to_list(length=CANDIDATES_PER_RETRIEVER)


async def semantic_candidates(chunks: AsyncCollection, file_id: ObjectId, query_vector: np.ndarray) -> list[dict]:
    rows = await chunks.find(
        {"file_id": file_id, "embedding": {"$exists": True}}, {"page": 1, "text": 1, "embedding": 1}
    ).to_list(length=None)
    if not rows:
        return []
    matrix = ai.from_bson_vectors([row["embedding"] for row in rows])
    if matrix.shape[1] != query_vector.shape[0]:
        log.warning("Embedding size mismatch for document %s; skipping semantic retrieval", file_id)
        return []
    scores = matrix @ query_vector
    return [rows[index] for index in np.argsort(-scores)[:CANDIDATES_PER_RETRIEVER]]


async def retrieve_chunks(
    chunks: AsyncCollection,
    file_id: ObjectId,
    query: str,
    query_vector: np.ndarray | None = None,
    limit: int = 6,
) -> list[dict]:
    keyword = await keyword_candidates(chunks, file_id, query)
    semantic = await semantic_candidates(chunks, file_id, query_vector) if query_vector is not None else []
    by_id = {row["_id"]: row for row in [*semantic, *keyword]}
    ranked = reciprocal_rank_fusion([[row["_id"] for row in semantic], [row["_id"] for row in keyword]])
    return [{"page": by_id[item]["page"], "text": by_id[item]["text"]} for item in ranked[:limit]]


async def query_vector_for(document: dict, query: str, settings: Settings) -> np.ndarray | None:
    """Embeds the query when this document's vectors match the current model; otherwise keyword-only."""
    if not (settings.ai_enabled and document.get("embedding_signature") == ai.embedding_signature(settings)):
        return None
    try:
        return await run_in_threadpool(ai.embed_query, query, settings)
    except ai.AIServiceError:
        log.exception("Query embedding failed; falling back to keyword search")
        return None


async def search_passages(
    chunks: AsyncCollection, document: dict, query: str, settings: Settings, limit: int = 10
) -> list[dict]:
    """Ranked passages for in-document search. No answer is generated, so this stays fast and free."""
    vector = await query_vector_for(document, query, settings)
    return await retrieve_chunks(chunks, document["_id"], query, vector, limit)


def excerpts_answer(sources: list[dict], preface: str) -> str:
    excerpts = "\n\n".join(f"Page {source['page']}: {source['text']}" for source in sources[:3])
    return f"{preface}\n\n{excerpts}"


async def answer(
    chunks: AsyncCollection, document: dict, question: str, history: list[dict], settings: Settings
) -> dict:
    semantic_ready = settings.ai_enabled and document.get("embedding_signature") == ai.embedding_signature(settings)
    search_query, query_vector = question, None

    if semantic_ready:
        try:
            if history:
                search_query = await run_in_threadpool(ai.standalone_question, question, history, settings)
            query_vector = await run_in_threadpool(ai.embed_query, search_query, settings)
        except ai.AIServiceError:
            log.exception("Query preparation failed; falling back to keyword retrieval")

    sources = await retrieve_chunks(chunks, document["_id"], search_query, query_vector, settings.retrieval_top_k)
    if not sources and search_query != question:
        sources = await retrieve_chunks(chunks, document["_id"], question, None, settings.retrieval_top_k)
    if not sources:
        return {
            "answer": "I couldn't find anything in this PDF related to your question. Try rephrasing it.",
            "sources": [],
            "mode": "none",
        }

    if not settings.ai_enabled:
        return {
            "answer": excerpts_answer(sources, "AI answers are turned off, so here are the most relevant passages."),
            "sources": sources,
            "mode": "extractive",
        }
    try:
        text = await run_in_threadpool(ai.generate_answer, question, history, sources, settings)
    except ai.AIServiceError:
        log.exception("Answer generation failed")
        return {
            "answer": excerpts_answer(sources, "The AI answer service is unavailable right now. Here are the most relevant passages."),
            "sources": sources,
            "mode": "extractive",
        }
    return {"answer": text, "sources": sources, "mode": "llm"}
