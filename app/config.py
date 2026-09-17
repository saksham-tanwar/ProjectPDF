import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    mongo_url: str = os.getenv("MONGO_URL", "mongodb://mongo:27017")
    mongo_database: str = os.getenv("MONGO_DATABASE", "paperchat")
    redis_url: str = os.getenv("REDIS_URL", "redis://valkey:6379/0")
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "/data/uploads"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
    worker_timeout: int = int(os.getenv("WORKER_TIMEOUT_SECONDS", "300"))
    cors_origins: tuple[str, ...] = tuple(origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()) or ("http://localhost:8000",)
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


settings = Settings()
