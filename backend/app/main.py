"""FastAPI application factory.

Wires cross-cutting concerns (CORS, routers) in one place. Business logic never
lives here; later milestones only add `include_router` lines and exception handlers.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import health, hearts, leaderboard, lessons, me, path, sessions
from app.core.config import get_settings
from app.core.errors import (
    AppError,
    app_error_handler,
    internal_error_handler,
    validation_error_handler,
)
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Create any missing tables before serving requests (idempotent).
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        lifespan=lifespan,
    )

    # The browser calls the API directly from another origin (localhost:3000 -> :8000),
    # so the API must explicitly allow that origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,  # mocked auth: no cookies are sent
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # One error envelope for everything: domain errors, bad requests, crashes.
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(path.router, prefix=settings.api_prefix)
    app.include_router(lessons.router, prefix=settings.api_prefix)
    app.include_router(sessions.router, prefix=settings.api_prefix)
    app.include_router(me.router, prefix=settings.api_prefix)
    app.include_router(leaderboard.router, prefix=settings.api_prefix)
    app.include_router(hearts.router, prefix=settings.api_prefix)
    return app


app = create_app()
