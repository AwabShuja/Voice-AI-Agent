from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from app.core.logging import log_event


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def validation_details(exc: ValidationError | RequestValidationError) -> list[dict]:
    # Do not echo input, exception objects, or provider credentials in error responses.
    return [
        {"field": ".".join(str(part) for part in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]


def error_response(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"data": None, "error": {"code": code, "message": message, "details": details}},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def application_error(request: Request, exc: AppError):
        return error_response(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def request_error(request: Request, exc: RequestValidationError):
        malformed = any(error["type"] == "json_invalid" for error in exc.errors())
        return error_response(
            400 if malformed else 422,
            "invalid_json" if malformed else "validation_error",
            "Malformed JSON." if malformed else "Please correct the indicated fields.",
            validation_details(exc),
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        # SQLAlchemy exceptions can contain bound demographic values; log only their type.
        log_event("request_failed", exception_type=type(exc).__name__, path=request.url.path)
        return error_response(500, "internal_error", "The request could not be completed.")
