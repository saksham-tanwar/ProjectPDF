import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request):
    state = request.app.state
    checks = {}
    try:
        await asyncio.wait_for(state.mongo_client.admin.command("ping"), timeout=3)
        checks["mongo"] = "ok"
    except Exception:
        checks["mongo"] = "unavailable"
    try:
        await asyncio.wait_for(state.redis.ping(), timeout=3)
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
    ready = all(value == "ok" for value in checks.values())
    return JSONResponse({"status": "ready" if ready else "degraded", "checks": checks}, status_code=200 if ready else 503)
