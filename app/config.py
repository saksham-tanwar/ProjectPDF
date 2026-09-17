"""Application settings, read from environment variables (and `.env` in development)."""
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1024, ge=256, le=3072)
    retrieval_top_k: int = Field(default=6, ge=1, le=20)
    openai_timeout_seconds: float = Field(default=45, gt=0)
    openai_max_output_tokens: int = Field(default=800, ge=50)

    max_upload_mb: int = Field(default=25, ge=1)
    max_pages: int = Field(default=500, ge=1)
    worker_timeout_seconds: int = Field(default=300, ge=30)
    user_max_documents: int = Field(default=50, ge=1)
    rate_limit_questions_per_minute: int = Field(default=20, ge=1)
    rate_limit_questions_per_day: int = Field(default=300, ge=1)
    rate_limit_uploads_per_hour: int = Field(default=20, ge=1)

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
            if not self.openai_api_key:
                problems.append("OPENAI_API_KEY is required in production (answers are generated with OpenAI)")
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
        return bool(self.openai_api_key)

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
