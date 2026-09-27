"""Request-level protections: body size limits, cross-site request checks, security headers, request logging."""
import logging
import time
import uuid

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings

log = logging.getLogger("paperchat.request")

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
MULTIPART_OVERHEAD = 64 * 1024
DEFAULT_BODY_LIMIT = 64 * 1024


class _BodyTooLarge(HTTPException):
    """An HTTPException so FastAPI's body parser re-raises it and the normal handler renders a 413."""

    def __init__(self, max_upload_mb: int):
        super().__init__(413, f"The upload is too large. The limit is {max_upload_mb} MB.")


class BodySizeLimitMiddleware:
    """Rejects oversized bodies before they are spooled to disk, including chunked uploads without Content-Length."""

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.upload_limit = settings.max_upload_bytes + MULTIPART_OVERHEAD
        self.max_upload_mb = settings.max_upload_mb

    def limit_for(self, scope: Scope) -> int:
        if scope["method"] == "POST" and scope["path"] == "/api/documents":
            return self.upload_limit
        return DEFAULT_BODY_LIMIT

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in UNSAFE_METHODS:
            await self.app(scope, receive, send)
            return
        limit = self.limit_for(scope)
        too_large = JSONResponse({"detail": f"The upload is too large. The limit is {self.max_upload_mb} MB."}, status_code=413)
        for name, value in scope["headers"]:
            if name == b"content-length" and value.isdigit() and int(value) > limit:
                await too_large(scope, receive, send)
                return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge(self.max_upload_mb)
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started:
                await too_large(scope, receive, send)


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self.allowed_origins = settings.allowed_origins
        self.csp = "; ".join([
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            "img-src 'self' data: https://*.googleusercontent.com",
            "connect-src 'self'",
            "font-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ])

    def is_cross_site(self, request: Request) -> bool:
        origin = request.headers.get("origin")
        if origin:
            return origin.rstrip("/") not in self.allowed_origins
        return request.headers.get("sec-fetch-site") == "cross-site"

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        started = time.perf_counter()
        if request.method in UNSAFE_METHODS and self.is_cross_site(request):
            response = JSONResponse({"detail": "Cross-site requests are not allowed."}, status_code=403)
        else:
            response = await call_next(request)

        path = request.url.path
        headers = response.headers
        headers["X-Request-ID"] = request_id
        headers["X-Content-Type-Options"] = "nosniff"
        headers["X-Frame-Options"] = "DENY"
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        if self.settings.is_production:
            headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        if not path.startswith("/docs") and not path.startswith("/redoc"):
            headers["Content-Security-Policy"] = self.csp
        if path.startswith("/api/") or path.startswith("/auth/"):
            headers["Cache-Control"] = "no-store"
        elif path.startswith("/assets/") and response.status_code == 200:
            headers["Cache-Control"] = "public, max-age=31536000, immutable"

        if path not in {"/healthz", "/readyz"}:
            log.info(
                "%s %s %s", request.method, path, response.status_code,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
        return response
