import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.errors import AppError, validation_details
from app.core.logging import log_event
from app.core.security import require_webhook_secret

router = APIRouter(prefix="/vapi", tags=["voice"], dependencies=[Depends(require_webhook_secret)])


class Webhook(BaseModel):
    # Vapi includes additional call metadata which the application intentionally ignores.
    model_config = ConfigDict(extra="ignore")
    message: dict[str, Any]


class CallContext(BaseModel):
    id: str = Field(min_length=1, max_length=200)


def tool_request(item: dict) -> tuple[str, dict]:
    """Accept Vapi's function wrapper and documented direct name/parameters variant."""
    function = item.get("function", item)
    if not isinstance(function, dict):
        raise AppError(400, "invalid_tool", "Malformed tool definition.")
    name = function.get("name")
    arguments = function.get("arguments", function.get("parameters", {}))
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise AppError(400, "invalid_arguments", "Tool arguments must be valid JSON.") from exc
    if not isinstance(name, str) or not isinstance(arguments, dict):
        raise AppError(400, "invalid_arguments", "Tool name and object arguments are required.")
    return name, arguments


@router.post("/webhook")
def webhook(payload: Webhook, request: Request):
    message = payload.message
    service = request.app.state.registration_service
    event_type = message.get("type")
    if event_type not in {"tool-calls", "end-of-call-report", "status-update"}:
        return {"received": True}
    try:
        call_id = CallContext.model_validate(message.get("call", {})).id
    except ValidationError as exc:
        raise AppError(422, "invalid_call", "A provider call ID is required.") from exc

    if event_type != "tool-calls":
        if event_type == "end-of-call-report" or message.get("status") == "ended":
            service.end_call(call_id)
        return {"received": True}

    calls = message.get("toolCallList", [])
    if not isinstance(calls, list) or not calls or len(calls) > 20:
        raise AppError(422, "invalid_tools", "Provide between 1 and 20 tool calls.")
    if any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in calls):
        raise AppError(422, "invalid_tools", "Every tool call must have an ID.")

    results = []
    for item in calls:
        try:
            name, arguments = tool_request(item)
            with request.app.state.session_factory() as session:
                output = service.execute(session, call_id, name, arguments)
            results.append({"toolCallId": item["id"], "result": json.dumps(output)})
        except (AppError, ValidationError) as exc:
            error = (
                {"code": exc.code, "message": exc.message, "details": exc.details}
                if isinstance(exc, AppError)
                else {
                    "code": "validation_error",
                    "message": "Correct the indicated fields.",
                    "details": validation_details(exc),
                }
            )
            results.append({"toolCallId": item["id"], "error": json.dumps(error)})
        except Exception as exc:
            log_event("voice_tool_failed", call_id=call_id, exception_type=type(exc).__name__)
            results.append(
                {
                    "toolCallId": item["id"],
                    "error": json.dumps(
                        {
                            "code": "save_unavailable",
                            "message": "I couldn't complete that request. "
                            "Do not say registration succeeded. Explain the problem and offer "
                            "one retry. If retrying a save, reuse the same token.",
                        }
                    ),
                }
            )
    # Vapi requires HTTP 200 with correlated string results/errors for synchronous tools.
    return {"results": results}
