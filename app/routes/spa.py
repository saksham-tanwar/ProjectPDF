"""Serves the built React app. API and auth paths never fall through to index.html."""
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter()

NOT_BUILT = """<!doctype html><title>Paperchat</title>
<p>The frontend hasn't been built. Run <code>npm run build</code> in <code>frontend/</code>,
or use the Vite dev server (<code>npm run dev</code>) on port 5173.</p>"""


@router.get("/{full_path:path}", include_in_schema=False)
async def spa(full_path: str, request: Request):
    if full_path.split("/", 1)[0] in {"api", "auth", "assets"}:
        raise HTTPException(404, "Not found")
    dist: Path = request.app.state.settings.frontend_dist_dir.resolve()
    index = dist / "index.html"
    if not index.exists():
        return HTMLResponse(NOT_BUILT, status_code=503)
    if full_path:
        candidate = (dist / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(dist):
            return FileResponse(candidate)
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
