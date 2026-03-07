from fastapi import FastAPI

from app.api.router import router as api_router
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()

    app = FastAPI(title=settings.app_name, version="0.1.0")
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
