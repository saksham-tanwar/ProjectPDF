"""Measures retrieval quality on a fixed question set, so changes can be compared instead of guessed at.

    python -m eval.runner                       # every configuration
    python -m eval.runner --configs keyword     # no AI provider needed
    python -m eval.runner --k 3 --json results.json

Indexes the synthetic corpus into a scratch MongoDB database (dropped and rebuilt each run), then runs the same
questions through each retrieval configuration and reports hit rate, MRR, nDCG and precision at k.
"""
import argparse
import asyncio
import statistics
import time
from pathlib import Path

import numpy as np
from bson import ObjectId

from app.config import Settings, get_settings
from app.db.client import create_async_client
from app.db.indexes import ensure_indexes
from app.queue.workers import extract_chunks
from app.services import rerank
from app.services.answering import (
    keyword_candidates,
    reciprocal_rank_fusion,
    semantic_candidates,
    semantic_first,
)
from eval.cache import EmbeddingCache
from eval.corpus import write_corpus
from eval.dataset import QUESTIONS
from eval.metrics import hit_rate, ndcg, precision, reciprocal_rank, summarise

HERE = Path(__file__).parent
SEMANTIC_WEIGHT = 1.0  # only used by the "hybrid" configuration; --semantic-weight overrides it
CONFIG_NAMES = [
    "keyword", "vector", "hybrid", "semantic-first",
    "keyword+rerank", "vector+rerank", "hybrid+rerank", "semantic-first+rerank",
]


async def index_corpus(db, settings: Settings, cache: EmbeddingCache | None, quiet: bool) -> dict[str, ObjectId]:
    paths = write_corpus(HERE / "corpus")
    await ensure_indexes(db)
    file_ids: dict[str, ObjectId] = {}
    for name, path in paths.items():
        file_id = ObjectId()
        pages, rows = extract_chunks(path, settings.max_pages)
        if cache is not None:
            for row, vector in zip(rows, cache.embed([row["text"] for row in rows])):
                row["embedding"] = ai_vector(vector)
        for row in rows:
            row["file_id"] = file_id
        await db.chunks.insert_many(rows)
        file_ids[name] = file_id
        if not quiet:
            print(f"  indexed {name}: {pages} pages, {len(rows)} passages")
    return file_ids


def ai_vector(vector: np.ndarray):
    from app.services.ai import to_bson_vector

    return to_bson_vector(vector)


async def retrieve(config: str, db, file_id: ObjectId, question: str, vector, settings: Settings, k: int) -> list[dict]:
    """Each configuration is spelled out here rather than hidden behind flags, so the comparison is unambiguous."""
    def passages(rows, limit):
        return [{"page": row["page"], "text": row["text"]} for row in rows[:limit]]

    if config.startswith("keyword"):
        rows = await keyword_candidates(db.chunks, file_id, question)
        shortlist = passages(rows, settings.rerank_candidates if config.endswith("+rerank") else k)
        return rerank.rerank(question, shortlist, settings, k) if config.endswith("+rerank") else shortlist
    if config.startswith("vector"):
        rows = await semantic_candidates(db.chunks, file_id, vector)
        shortlist = passages(rows, settings.rerank_candidates if config.endswith("+rerank") else k)
        return rerank.rerank(question, shortlist, settings, k) if config.endswith("+rerank") else shortlist

    keyword = await keyword_candidates(db.chunks, file_id, question)
    semantic = await semantic_candidates(db.chunks, file_id, vector) if vector is not None else []
    by_id = {row["_id"]: row for row in [*semantic, *keyword]}
    if config.startswith("semantic-first"):
        fused = semantic_first([row["_id"] for row in semantic], [row["_id"] for row in keyword])
    else:
        fused = reciprocal_rank_fusion(
            [[row["_id"] for row in semantic], [row["_id"] for row in keyword]],
            weights=[SEMANTIC_WEIGHT, 1.0],
        )
    if not config.endswith("+rerank"):
        return [{"page": by_id[item]["page"], "text": by_id[item]["text"]} for item in fused[:k]]

    shortlist = [{"page": by_id[item]["page"], "text": by_id[item]["text"]} for item in fused[:settings.rerank_candidates]]
    return rerank.rerank(question, shortlist, settings, k)


async def evaluate(configs: list[str], k: int, quiet: bool) -> dict:
    settings = get_settings()
    needs_vectors = any(not config.startswith("keyword") for config in configs)
    if needs_vectors and not settings.ai_enabled:
        raise SystemExit("These configurations need embeddings: set AI_API_KEY, or run with --configs keyword")
    if any(config.endswith("+rerank") for config in configs) and settings.rerank_mode == "never":
        raise SystemExit("Reranking is turned off: set RERANK_MODE=always or lexical-only")

    cache = EmbeddingCache(HERE / "cache" / "embeddings.npz", settings) if needs_vectors else None
    client = create_async_client(settings)
    database = client[f"{settings.mongo_database}_eval"]
    await client.drop_database(database.name)
    try:
        if not quiet:
            print(f"Indexing corpus into {database.name}")
        file_ids = await index_corpus(database, settings, cache, quiet)
        vectors = {}
        if cache is not None:
            question_vectors = cache.embed([question.text for question in QUESTIONS])
            vectors = {question.text: vector for question, vector in zip(QUESTIONS, question_vectors)}
            cache.save()
            if not quiet:
                print(f"  embeddings: {cache.hits} cached, {cache.misses} fetched\n")

        results = {}
        for config in configs:
            rows, durations = [], []
            for question in QUESTIONS:
                started = time.perf_counter()
                passages = await retrieve(
                    config, database, file_ids[question.document], question.text, vectors.get(question.text), settings, k
                )
                durations.append((time.perf_counter() - started) * 1000)
                pages = [passage["page"] for passage in passages]
                relevant = question.pages
                rows.append({
                    "question": question.text,
                    "document": question.document,
                    "keyword_friendly": question.keyword_friendly,
                    "expected": sorted(relevant),
                    "retrieved": pages,
                    "hit_rate": hit_rate(pages, relevant, k),
                    "mrr": reciprocal_rank(pages, relevant, k),
                    "ndcg": ndcg(pages, relevant, k),
                    "precision": precision(pages, relevant, k),
                })
            results[config] = {
                "overall": summarise(rows),
                "paraphrased": summarise([row for row in rows if not row["keyword_friendly"]]),
                "same_wording": summarise([row for row in rows if row["keyword_friendly"]]),
                "median_ms": statistics.median(durations),
                "questions": rows,
            }
        return {"k": k, "questions": len(QUESTIONS), "configs": results, "settings": describe(settings)}
    finally:
        await client.drop_database(database.name)
        await client.close()


def describe(settings: Settings) -> dict:
    return {
        "semantic_weight": SEMANTIC_WEIGHT,
        "embedding_model": settings.ai_embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
        "reranker_model": settings.reranker_model,
        "rerank_mode": settings.rerank_mode,
        "rerank_candidates": settings.rerank_candidates,
    }


def report(results: dict) -> str:
    k = results["k"]
    lines = [
        f"Retrieval quality over {results['questions']} questions (k={k})",
        "",
        f"| config | hit@{k} | MRR@{k} | nDCG@{k} | P@{k} | paraphrased hit@{k} | same-wording hit@{k} | median ms |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, data in results["configs"].items():
        overall = data["overall"]
        lines.append(
            f"| {name} | {overall['hit_rate']:.2f} | {overall['mrr']:.2f} | {overall['ndcg']:.2f} | "
            f"{overall['precision']:.2f} | {data['paraphrased']['hit_rate']:.2f} | "
            f"{data['same_wording']['hit_rate']:.2f} | {data['median_ms']:.0f} |"
        )
    return "\n".join(lines)


def misses(results: dict, config: str, limit: int = 5) -> str:
    rows = [row for row in results["configs"][config]["questions"] if row["hit_rate"] == 0][:limit]
    if not rows:
        return f"\n{config}: no misses."
    lines = [f"\n{config} missed {len(rows)} question(s):"]
    for row in rows:
        lines.append(f"  - {row['question']}  (expected p{row['expected']}, got p{row['retrieved']})")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--configs", default=",".join(CONFIG_NAMES), help=f"comma separated: {', '.join(CONFIG_NAMES)}")
    parser.add_argument("--k", type=int, default=5, help="how many passages a retriever may return")
    parser.add_argument("--json", type=Path, help="also write the full per-question results here")
    parser.add_argument("--semantic-weight", type=float, help="how much semantic outweighs keyword when fusing")
    parser.add_argument("--quiet", action="store_true")
    arguments = parser.parse_args()

    configs = [name.strip() for name in arguments.configs.split(",") if name.strip()]
    unknown = [name for name in configs if name not in CONFIG_NAMES]
    if unknown:
        raise SystemExit(f"Unknown configuration(s): {', '.join(unknown)}. Choose from {', '.join(CONFIG_NAMES)}")

    if arguments.semantic_weight is not None:
        global SEMANTIC_WEIGHT
        SEMANTIC_WEIGHT = arguments.semantic_weight
    results = asyncio.run(evaluate(configs, arguments.k, arguments.quiet))
    print(report(results))
    for config in configs:
        print(misses(results, config))
    if arguments.json:
        import json

        arguments.json.parent.mkdir(parents=True, exist_ok=True)
        arguments.json.write_text(json.dumps(results, indent=2))
        print(f"\nWrote {arguments.json}")


if __name__ == "__main__":
    main()
