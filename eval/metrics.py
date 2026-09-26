"""Retrieval metrics. Relevance is binary: a retrieved passage counts if it comes from a page that answers the question."""
from math import log2


def hit_rate(ranked_pages: list[int], relevant: set[int], k: int) -> float:
    """1.0 if any answering page appears in the top k. Also called recall@k for single-answer questions."""
    return float(any(page in relevant for page in ranked_pages[:k]))


def reciprocal_rank(ranked_pages: list[int], relevant: set[int], k: int) -> float:
    """1/rank of the first answering page, so a correct hit at position 1 scores far higher than at position 5."""
    for index, page in enumerate(ranked_pages[:k], start=1):
        if page in relevant:
            return 1.0 / index
    return 0.0


def ndcg(ranked_pages: list[int], relevant: set[int], k: int) -> float:
    """Discounted gain over the ideal ordering; rewards putting every answering page near the top."""
    gain = sum(1.0 / log2(index + 1) for index, page in enumerate(ranked_pages[:k], start=1) if page in relevant)
    ideal = sum(1.0 / log2(index + 1) for index in range(1, min(len(relevant), k) + 1))
    return gain / ideal if ideal else 0.0


def precision(ranked_pages: list[int], relevant: set[int], k: int) -> float:
    top = ranked_pages[:k]
    return sum(page in relevant for page in top) / len(top) if top else 0.0


def summarise(per_question: list[dict]) -> dict:
    """Averages each metric across questions; `mean` of an empty list would be a lie, so callers pass real results."""
    keys = ["hit_rate", "mrr", "ndcg", "precision"]
    return {key: sum(row[key] for row in per_question) / len(per_question) for key in keys}
