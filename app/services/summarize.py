"""Document summarization: hierarchical (map-reduce) so PDFs far larger than the model's context still work."""
import logging
import re

from app.config import Settings
from app.services import ai

log = logging.getLogger(__name__)

BATCH_CHARS = 12_000
# Most PDFs fit in a modern model's context, and one pass keeps far more detail than map-reduce.
SINGLE_PASS_CHARS = 120_000
MAX_ROUNDS = 3
BULLET = re.compile(r"^\s*[•\-\*•]\s*")

SECTION_INSTRUCTIONS = """You are condensing part of a document so it can be summarised later.
Write a tight factual note (at most 120 words) covering what this part actually says: topics, claims, figures, names, conclusions.
Start with the page range in square brackets, e.g. [pages 3-5]. No preamble, no opinions, plain text."""

SUMMARY_INSTRUCTIONS = """You are summarising a document for someone who has not read it.
Write:
1. An overview of 3 to 5 sentences: what the document is, who it is for and what it actually says.
2. Then "KEY POINTS:" on its own line, followed by 4 to 8 bullets starting with "• ".
Each bullet states one concrete point and ends with its page reference, like [p. 4].
Be specific: name the actual topics, projects, technologies, people, figures and conclusions in the text.
Never hedge with phrases like "appears to be", "various aspects", "several topics" or "different areas" — say which ones.
Use only the material provided. Plain text, no Markdown, no headings other than KEY POINTS."""


def batch_chunks(chunks: list[dict], batch_chars: int = BATCH_CHARS) -> list[str]:
    """Groups consecutive passages into blocks small enough to summarise, labelled with their page range."""
    batches, current, size = [], [], 0
    for chunk in chunks:
        if current and size + len(chunk["text"]) > batch_chars:
            batches.append(current)
            current, size = [], 0
        current.append(chunk)
        size += len(chunk["text"])
    if current:
        batches.append(current)
    return [
        f"[pages {batch[0]['page']}-{batch[-1]['page']}]\n"
        # Each passage keeps its own page marker so the summary can cite exact pages, not just the block's range.
        + "\n\n".join(f"[p. {chunk['page']}] {chunk['text']}" for chunk in batch)
        for batch in batches
    ]


def parse_key_points(text: str) -> tuple[str, list[str]]:
    """Splits the model's reply into the overview and the bullet list, tolerating a missing KEY POINTS header."""
    head, _, tail = text.partition("KEY POINTS:")
    overview = head.strip()
    points = [BULLET.sub("", line).strip() for line in tail.splitlines() if BULLET.match(line)]
    if not points:
        points = [BULLET.sub("", line).strip() for line in overview.splitlines() if BULLET.match(line)]
        overview = "\n".join(line for line in overview.splitlines() if not BULLET.match(line)).strip()
    return overview, [point for point in points if point]


def _fits_in_one_pass(chunks: list[dict]) -> bool:
    return sum(len(chunk["text"]) for chunk in chunks) <= SINGLE_PASS_CHARS


def summarize_document(chunks: list[dict], settings: Settings) -> dict:
    """Returns {"summary", "key_points"}. Raises AIServiceError if the provider fails."""
    blocks = batch_chunks(chunks, batch_chars=SINGLE_PASS_CHARS) if _fits_in_one_pass(chunks) else batch_chunks(chunks)
    rounds = 0
    while len(blocks) > 1 and rounds < MAX_ROUNDS:
        notes = [
            ai.complete(
                [{"role": "system", "content": SECTION_INSTRUCTIONS}, {"role": "user", "content": block}],
                settings,
                # Reasoning models spend part of this budget thinking; too small a cap truncates the note mid-sentence.
                max_tokens=settings.ai_max_output_tokens,
                purpose="Section summary",
            )
            for block in blocks
        ]
        blocks = batch_chunks([{"page": index + 1, "text": note} for index, note in enumerate(notes)])
        rounds += 1
        log.info("Summarisation round %s produced %s block(s)", rounds, len(blocks))

    text = ai.complete(
        [{"role": "system", "content": SUMMARY_INSTRUCTIONS}, {"role": "user", "content": blocks[0]}],
        settings,
        max_tokens=settings.ai_max_output_tokens,
        purpose="Document summary",
    )
    overview, key_points = parse_key_points(text)
    return {"summary": overview, "key_points": key_points}
