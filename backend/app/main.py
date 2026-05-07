from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.evaluations import router as evaluations_router
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.rate_limiting import RateLimitMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        RateLimitMiddleware,
        enabled=settings.rate_limit_enabled,
        requests_per_window=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    app.add_middleware(RequestContextMiddleware, request_id_header=settings.request_id_header)
    app.include_router(evaluations_router)
    app.include_router(health_router)
    app.include_router(imports_router)

    return app


app = create_app()
