import os
import re

from app.config import settings


def terms(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-zA-Z0-9]{3,}", value.lower())}


async def retrieve_chunks(collection, file_id, question: str, limit: int = 5) -> list[dict]:
    query = terms(question)
    candidates = await collection.find({"file_id": file_id}, {"_id": 0, "page": 1, "text": 1}).to_list(length=500)
    ranked = sorted(candidates, key=lambda item: len(query & terms(item["text"])), reverse=True)
    return [item for item in ranked[:limit] if query & terms(item["text"])]


def answer_question(question: str, sources: list[dict]) -> tuple[str, str]:
    if not os.getenv("OPENAI_API_KEY"):
        excerpts = "\n\n".join(f"Page {source['page']}: {source['text']}" for source in sources[:3])
        return f"OpenAI is not configured, so here are the most relevant excerpts:\n\n{excerpts}", "extractive"
    context = "\n\n".join(f"[Page {source['page']}] {source['text']}" for source in sources)
    # Import only when generation is enabled; extractive mode has no LLM dependency at runtime.
    from openai import OpenAI
    response = OpenAI().responses.create(
        model=settings.openai_model,
        input=f"Answer only from the supplied PDF excerpts. If they do not answer the question, say so. Cite pages like [p. 2].\n\nQuestion: {question}\n\nExcerpts:\n{context}",
    )
    return response.output_text, "llm"
