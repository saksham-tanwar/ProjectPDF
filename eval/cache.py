"""On-disk embedding cache, so repeated evaluation runs cost nothing and work offline."""
import hashlib
import json
from pathlib import Path

import numpy as np

from app.config import Settings
from app.services import ai


class EmbeddingCache:
    def __init__(self, path: Path, settings: Settings):
        self.path = path
        self.settings = settings
        self.vectors: dict[str, np.ndarray] = {}
        self.hits = self.misses = 0
        if path.exists():
            with np.load(path) as stored:
                self.vectors = {key: stored[key] for key in stored.files}

    def _key(self, text: str) -> str:
        fingerprint = f"{self.settings.ai_embedding_model}:{self.settings.embedding_dimensions}:{text}"
        return hashlib.sha1(fingerprint.encode()).hexdigest()

    def embed(self, texts: list[str]) -> np.ndarray:
        keys = [self._key(text) for text in texts]
        missing = [text for text, key in zip(texts, keys) if key not in self.vectors]
        if missing:
            fresh = ai.embed_texts(missing, self.settings)
            for text, vector in zip(missing, fresh):
                self.vectors[self._key(text)] = vector
            self.misses += len(missing)
        self.hits += len(texts) - len(missing)
        return np.stack([self.vectors[key] for key in keys])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(self.path, **self.vectors)
        meta = {
            "model": self.settings.ai_embedding_model,
            "dimensions": self.settings.embedding_dimensions,
            "entries": len(self.vectors),
        }
        self.path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
