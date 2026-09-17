"""Web entry point: `python -m app.main`. Honours $PORT and proxy settings for hosted platforms."""
import uvicorn

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    reload = settings.app_env == "development"
    uvicorn.run(
        "app.server:app",
        host="0.0.0.0",
        port=settings.port,
        proxy_headers=True,
        forwarded_allow_ips=settings.forwarded_allow_ips,
        reload=reload,
        workers=None if reload else settings.web_concurrency,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
