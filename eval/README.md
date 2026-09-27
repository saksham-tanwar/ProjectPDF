# Retrieval evaluation

Retrieval is the part of this app that decides whether an answer can be right at all: if the passages are wrong, no
model can recover. This harness measures it on a fixed question set so changes can be compared instead of guessed at.

```bash
python -m eval.runner                          # every configuration
python -m eval.runner --configs keyword        # no AI provider needed
python -m eval.runner --k 3 --json out.json    # different cut-off, full per-question output
```

The runner indexes a synthetic corpus into a scratch MongoDB database (`<MONGO_DATABASE>_eval`, dropped and rebuilt
each run), then puts the same questions through each retrieval configuration.

## What is measured

- **hit@k** — the share of questions where an answering page appears in the top k. Recall, in other words.
- **MRR@k** — 1/rank of the first answering page. Rewards putting the right passage *first*, which matters because
  the answer model reads the top passages and is influenced most by the first.
- **nDCG@k** — like MRR but credits every answering page, discounted by position.
- **P@k** — precision. With one answering page per question the ceiling is 1/k, so it is only useful for comparing
  configurations against each other.
- **paraphrased vs same-wording** — the question set is split by whether the question shares wording with the page.
  This is where lexical and semantic retrieval separate.

## Corpus and questions

Three documents (a product manual, an HR policy, a research paper) written in [corpus.py](corpus.py), 39 pages in
total, with deliberate distractor pages: cover for accessories next to cover for the machine, expenses next to
working abroad, results next to results by city size. Without distractors every retriever looks perfect and the
measurement says nothing.

[dataset.py](dataset.py) holds 51 questions, each naming the page that answers it **by page title**, so inserting a
page cannot silently invalidate the golden set. Most questions are worded differently from the document; 20 share
wording, including exact-term lookups such as an email address or "9 bar".

The questions and the answering pages were written by hand for this corpus. They are the harness's main limitation:
they were authored alongside the system they test, and 51 questions over 39 pages is small. Treat the numbers as a
regression check and a way to compare configurations, not as a claim about PDFs in general.

## Results

51 questions, k=5, `gemini-embedding-001` at 768 dimensions, reranker `Xenova/ms-marco-MiniLM-L-6-v2`:

| config | hit@5 | MRR@5 | nDCG@5 | paraphrased hit@5 | same-wording hit@5 | median ms |
| --- | --- | --- | --- | --- | --- | --- |
| keyword | 0.73 | 0.67 | 0.68 | 0.62 | 0.89 | 2 |
| vector | 1.00 | 0.96 | 0.97 | 1.00 | 1.00 | 3 |
| hybrid (rank fusion) | 0.98 | 0.84 | 0.88 | 0.97 | 1.00 | 4 |
| **semantic-first (default)** | **1.00** | **0.96** | **0.97** | 1.00 | 1.00 | 3 |
| keyword+rerank | 0.76 | 0.71 | 0.73 | 0.69 | 0.89 | 77 |
| vector+rerank | 1.00 | 0.87 | 0.90 | 1.00 | 1.00 | 432 |
| hybrid+rerank | 1.00 | 0.87 | 0.90 | 1.00 | 1.00 | 469 |
| semantic-first+rerank | 1.00 | 0.87 | 0.90 | 1.00 | 1.00 | 446 |

Three findings, two of which contradicted the design the app shipped with:

1. **Keyword search alone is weak on natural questions** (0.62 hit@5 on paraphrased questions vs 0.89 when the
   question shares wording). Expected, and the reason embeddings exist.
2. **Rank fusion was making things worse.** Hybrid scored MRR 0.84 against 0.96 for vectors alone: with equal
   weights, a tail of literal matches outvotes a strong semantic hit. "What voids the warranty?" is the clearest
   case — the word *voids* appears on the cleaning page, not the cover page. Weighting semantic up to 8× only
   recovered 0.86, because a page ranked well by *both* retrievers still overtakes the best semantic hit.
   Keeping the semantic order and appending keyword-only hits below it ("semantic-first") preserves vector precision
   at MRR 0.96 while retaining keyword recall as a backstop.
3. **The cross-encoder reranker is worse than the embedding model here.** It drops MRR from 0.96 to 0.87 and adds
   ~400 ms. It clearly helps lexical retrieval (0.67 → 0.71), which is the path used when a document has no usable
   embeddings. Hence the default `RERANK_MODE=lexical-only`: rerank when there is no query vector, otherwise don't.

A larger reranker (`BAAI/bge-reranker-base`, ~1 GB) would likely beat the MiniLM model, at a memory cost that does
not fit a small instance. That is the obvious next experiment, and this harness is how it should be settled.

## Cost

Embeddings are cached in `eval/cache/` and keyed by model, size and text, so repeat runs make no API calls. The first
run embeds 39 passages and 51 questions once.
