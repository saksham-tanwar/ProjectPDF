"""Application factory: HTTP API, Google sign-in, and the built React frontend on one origin."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from starlette.middleware.sessions import SessionMiddleware

from app.config import Settings, get_settings
from app.db.client import create_async_client
from app.db.indexes import ensure_indexes
from app.log_config import configure_logging
from app.queue.q import create_queue
from app.routes import auth, documents, health, spa
from app.security import BodySizeLimitMiddleware, SecurityMiddleware
from app.services.storage import create_storage

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, *, queue=None, redis=None, storage=None) -> FastAPI:
    """Build the app. Tests inject `queue`, `redis` and `storage`; production creates them from settings."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state = app.state
        state.mongo_client = create_async_client(settings)
        state.db = state.mongo_client[settings.mongo_database]
        state.redis = redis or AsyncRedis.from_url(settings.redis_url, socket_connect_timeout=5, health_check_interval=30)
        sync_redis = None
        if queue is None:
            sync_redis = Redis.from_url(settings.redis_url, socket_connect_timeout=5, health_check_interval=30)
        state.queue = queue or create_queue(sync_redis, settings)
        state.storage = storage or create_storage(settings)
        state.oauth = auth.create_oauth(settings)
        if settings.run_worker_in_web and queue is None:
            from app.worker import start_in_thread

            state.worker_thread = start_in_thread(settings)
        try:
            await ensure_indexes(state.db)
        except Exception:
            # Keep serving so /readyz can report the problem; requests needing Mongo will fail individually.
            log.exception("Could not ensure MongoDB indexes")
        yield
        await state.mongo_client.close()
        if redis is None:
            await state.redis.aclose()
        if sync_redis is not None:
            sync_redis.close()

    app = FastAPI(
        title="Paperchat",
        version="2.0.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.state.settings = settings

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(documents.router)
    assets = settings.frontend_dist_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    app.include_router(spa.router)

    # Middleware runs outermost-last-added: body limit → security → sessions → CORS → routes.
    if settings.cors_origins.strip():
        app.add_middleware(
            CORSMiddleware,
            allow_origins=sorted(settings.allowed_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type"],
        )
    app.add_middleware(
        SessionMiddleware,  # Only holds short-lived OAuth state; login sessions use their own cookie.
        secret_key=settings.effective_session_secret,
        session_cookie="paperchat_oauth",
        max_age=600,
        same_site="lax",
        https_only=settings.public_base_url.startswith("https://"),
    )
    app.add_middleware(SecurityMiddleware, settings=settings)
    app.add_middleware(BodySizeLimitMiddleware, settings=settings)
    return app


def _app_from_environment() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    return create_app(settings)


app = _app_from_environment()
