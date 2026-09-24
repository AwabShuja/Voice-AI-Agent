import secrets
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AppError

api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
webhook_scheme = HTTPBearer(auto_error=False, scheme_name="VapiWebhookBearer")


def require_api_key(request: Request, key: Annotated[str | None, Depends(api_key_scheme)]) -> None:
    expected = request.app.state.settings.api_key.get_secret_value()
    if key is None or not secrets.compare_digest(key.encode(), expected.encode()):
        raise AppError(401, "unauthorized", "A valid X-API-Key header is required.")


def require_webhook_secret(
    request: Request,
    credential: Annotated[HTTPAuthorizationCredentials | None, Depends(webhook_scheme)],
) -> None:
    expected = request.app.state.settings.vapi_webhook_secret.get_secret_value()
    if credential is None or not secrets.compare_digest(
        credential.credentials.encode(), expected.encode()
    ):
        raise AppError(401, "unauthorized", "A valid webhook bearer token is required.")
