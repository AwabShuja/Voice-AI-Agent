from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any = None


class ApiResponse[T](BaseModel):
    data: T | None = None
    error: ErrorDetail | None = None
