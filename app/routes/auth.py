import logging

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pymongo.asynchronous.database import AsyncDatabase

from app.config import Settings
from app.deps import get_db, get_settings
from app.services.auth import (
    clear_session_cookie,
    create_session,
    delete_session,
    public_user,
    session_token,
    set_session_cookie,
    upsert_user,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth")


def create_oauth(settings: Settings) -> OAuth:
    oauth = OAuth()
    if settings.google_enabled:
        oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile", "timeout": 10},
        )
    return oauth


@router.get("/google/login")
async def google_login(request: Request, settings: Settings = Depends(get_settings)):
    if not settings.google_enabled:
        raise HTTPException(404, "Google sign-in is not configured.")
    redirect_uri = f"{settings.public_base_url}/auth/google/callback"
    return await request.app.state.oauth.google.authorize_redirect(request, redirect_uri, prompt="select_account")


@router.get("/google/callback")
async def google_callback(
    request: Request, db: AsyncDatabase = Depends(get_db), settings: Settings = Depends(get_settings)
):
    if not settings.google_enabled:
        raise HTTPException(404, "Google sign-in is not configured.")
    try:
        token = await request.app.state.oauth.google.authorize_access_token(request)
    except OAuthError as error:
        log.warning("Google sign-in failed: %s", error.error)
        return RedirectResponse("/login?error=google", status_code=303)
    info = token.get("userinfo") or {}
    if not info.get("sub") or not info.get("email") or not info.get("email_verified"):
        return RedirectResponse("/login?error=unverified", status_code=303)
    user = await upsert_user(
        db,
        provider="google",
        provider_id=info["sub"],
        email=info["email"],
        name=info.get("name") or info["email"],
        picture=info.get("picture"),
    )
    response = RedirectResponse("/", status_code=303)
    set_session_cookie(response, await create_session(db, user["_id"], settings), settings)
    return response


@router.post("/dev-login")
async def dev_login(db: AsyncDatabase = Depends(get_db), settings: Settings = Depends(get_settings)):
    if settings.is_production or not settings.dev_login_enabled:
        raise HTTPException(404, "Not found")
    user = await upsert_user(
        db, provider="dev", provider_id="developer", email="developer@localhost", name="Local developer", picture=None
    )
    response = Response(status_code=204)
    set_session_cookie(response, await create_session(db, user["_id"], settings), settings)
    return response


@router.post("/logout", status_code=204)
async def logout(request: Request, db: AsyncDatabase = Depends(get_db), settings: Settings = Depends(get_settings)):
    await delete_session(db, session_token(request))
    response = Response(status_code=204)
    clear_session_cookie(response, settings)
    return response
