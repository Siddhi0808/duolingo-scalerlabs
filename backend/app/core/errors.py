"""Application errors and the single JSON error envelope.

Services raise these (they never import FastAPI); handlers in main.py turn them into:

    {"error": {"code": "LESSON_LOCKED", "message": "...", "details": {...}}}

The frontend branches on the stable `code`, never on the human-readable message.
Request-validation errors and unexpected exceptions use the same envelope.
"""

import logging
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("lingo")


class AppError(Exception):
    status_code = 400

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class ForbiddenError(AppError):
    """The resource exists but the learner may not use it yet (e.g. a locked lesson)."""

    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    """The request is valid but conflicts with the current state (e.g. session ended)."""

    status_code = 409


class UnprocessableError(AppError):
    """Well-formed JSON that makes no sense for this resource (e.g. unknown option id)."""

    status_code = 422


class SetupError(AppError):
    """The server is not ready (e.g. the database has not been seeded)."""

    status_code = 503


def _envelope(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


async def app_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return _envelope(exc.status_code, exc.code, exc.message, exc.details)


async def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = jsonable_encoder(exc.errors(), exclude={"input", "ctx", "url"})
    return _envelope(422, "VALIDATION_ERROR", "The request body is invalid.", {"errors": errors})


async def internal_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return _envelope(500, "INTERNAL_ERROR", "Something went wrong. Please try again.")
