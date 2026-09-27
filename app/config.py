"""Application settings, read from environment variables (and `.env` in development)."""
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    app_env: Literal["development", "production", "test"] = "development"
    public_base_url: str = "http://localhost:8000"
    port: int = 8000
    web_concurrency: int = Field(default=1, ge=1)
    forwarded_allow_ips: str = "127.0.0.1"
    log_level: str = "INFO"

    mongo_url: str = "mongodb://localhost:27017"
    mongo_database: str = "paperchat"
    redis_url: str = "redis://localhost:6379/0"

    storage_backend: Literal["local", "s3"] = "local"
    upload_dir: Path = REPO_ROOT / ".runtime" / "uploads"
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = "auto"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""

    session_secret: str = ""
    session_ttl_days: int = Field(default=14, ge=1)
    google_client_id: str = ""
    google_client_secret: str = ""
    dev_login_enabled: bool = False

    # Any OpenAI-compatible API: OpenAI by default, or e.g. Gemini via AI_BASE_URL. OPENAI_* names are accepted too.
    ai_api_key: str = Field(default="", validation_alias=AliasChoices("AI_API_KEY", "OPENAI_API_KEY"))
    ai_base_url: str = Field(default="", validation_alias=AliasChoices("AI_BASE_URL", "OPENAI_BASE_URL"))
    ai_chat_model: str = Field(default="gpt-4.1-mini", validation_alias=AliasChoices("AI_CHAT_MODEL", "OPENAI_MODEL"))
    ai_embedding_model: str = Field(
        default="text-embedding-3-small", validation_alias=AliasChoices("AI_EMBEDDING_MODEL", "OPENAI_EMBEDDING_MODEL")
    )
    # Sent only when set; use for reasoning models (e.g. "low" for Gemini) so thinking doesn't eat the answer budget.
    ai_reasoning_effort: str = Field(default="", validation_alias=AliasChoices("AI_REASONING_EFFORT"))
    ai_timeout_seconds: float = Field(
        default=45, gt=0, validation_alias=AliasChoices("AI_TIMEOUT_SECONDS", "OPENAI_TIMEOUT_SECONDS")
    )
    ai_max_output_tokens: int = Field(
        default=1200, ge=50, validation_alias=AliasChoices("AI_MAX_OUTPUT_TOKENS", "OPENAI_MAX_OUTPUT_TOKENS")
    )
    embedding_dimensions: int = Field(default=1024, ge=256, le=3072)
    retrieval_top_k: int = Field(default=6, ge=1, le=20)

    # Local cross-encoder reranking (~110 MB, no API calls). Measured in eval/README.md: the small cross-encoder
    # improves lexical-only retrieval but ranks worse than the embedding model when embeddings are available,
    # so by default it runs only when there is no query vector. "always" and "never" are the other options.
    rerank_mode: Literal["never", "lexical-only", "always"] = "lexical-only"
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    reranker_threads: int = Field(default=1, ge=1)
    rerank_candidates: int = Field(default=20, ge=2, le=100)
    rerank_max_chars: int = Field(default=2_000, ge=200)
    model_cache_dir: Path = REPO_ROOT / ".runtime" / "models"

    max_upload_mb: int = Field(default=25, ge=1)
    max_pages: int = Field(default=500, ge=1)
    worker_timeout_seconds: int = Field(default=300, ge=30)
    user_max_documents: int = Field(default=50, ge=1)
    rate_limit_questions_per_minute: int = Field(default=20, ge=1)
    rate_limit_questions_per_day: int = Field(default=300, ge=1)
    rate_limit_uploads_per_hour: int = Field(default=20, ge=1)
    rate_limit_searches_per_minute: int = Field(default=60, ge=1)
    rate_limit_summaries_per_hour: int = Field(default=10, ge=1)

    cors_origins: str = ""
    frontend_dist_dir: Path = REPO_ROOT / "frontend" / "dist"

    @field_validator("public_base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_for_environment(self) -> "Settings":
        problems = []
        if self.storage_backend == "s3" and not (self.s3_bucket and self.s3_access_key_id and self.s3_secret_access_key):
            problems.append("STORAGE_BACKEND=s3 requires S3_BUCKET, S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY")
        if self.is_production:
            if not self.public_base_url.startswith("https://"):
                problems.append("PUBLIC_BASE_URL must be an https:// URL in production")
            if len(self.session_secret) < 32:
                problems.append("SESSION_SECRET must be at least 32 characters in production")
            if not self.ai_api_key:
                problems.append("AI_API_KEY is required in production (embeddings and answers need an AI provider)")
            if not (self.google_client_id and self.google_client_secret):
                problems.append("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required in production")
            if self.dev_login_enabled:
                problems.append("DEV_LOGIN_ENABLED must not be set in production")
            if self.storage_backend != "s3":
                problems.append("STORAGE_BACKEND must be s3 in production (web and worker run on separate machines)")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_api_key)

    @property
    def ai_provider(self) -> str:
        host = urlsplit(self.ai_base_url).hostname or "api.openai.com"
        if host == "openai.com" or host.endswith(".openai.com"):
            return "OpenAI"
        if host.endswith("googleapis.com"):
            return "Google Gemini"
        return host

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def public_origin(self) -> str:
        parts = urlsplit(self.public_base_url)
        return f"{parts.scheme}://{parts.netloc}"

    @property
    def allowed_origins(self) -> set[str]:
        extra = {origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()}
        return {self.public_origin} | extra

    @property
    def effective_session_secret(self) -> str:
        # Development gets a fixed fallback so local logins survive reloads; production validation forbids it.
        return self.session_secret or "development-only-session-secret-change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()
