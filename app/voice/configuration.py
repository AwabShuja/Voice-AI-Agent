from copy import deepcopy
from pathlib import Path

from app.schemas.patient import PatientUpdate
from app.voice.contracts import SaveRegistration


def inline_schema(schema: dict) -> dict:
    """Inline Pydantic references so each provider tool has a self-contained JSON schema."""
    definitions = schema.get("$defs", {})

    def expand(node):
        if isinstance(node, list):
            return [expand(value) for value in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return expand(deepcopy(definitions[node["$ref"].split("/")[-1]]))
        return {key: expand(value) for key, value in node.items() if key not in {"$defs", "title"}}

    return expand(schema)


def assistant_configuration(base_url: str, credential_id: str, model: str) -> dict:
    server = {
        "url": f"{base_url.rstrip('/')}/vapi/webhook",
        "credentialId": credential_id,
        "timeoutSeconds": 15,
    }
    fields_schema = inline_schema(PatientUpdate.model_json_schema())
    empty_schema = {"type": "object", "properties": {}, "additionalProperties": False}
    specs = [
        (
            "update_registration",
            "Record newly supplied or corrected demographics. "
            "Returns field errors and missing fields. "
            "Invalidates any previous confirmation. Send only supplied fields.",
            {
                "type": "object",
                "properties": {"fields": fields_schema},
                "required": ["fields"],
                "additionalProperties": False,
            },
        ),
        (
            "prepare_registration",
            "Validate the full draft and get every detail for readback plus a confirmation token. "
            "Offer optional fields first. Read ALL returned details, ask consent, and wait.",
            empty_schema,
        ),
        (
            "save_registration",
            "Only after full readback and a NEW explicit caller confirmation, "
            "save the prepared draft. "
            "Use its exact token. Do not call in the same assistant turn as readback. "
            "Announce success only if status is saved. Reuse the token for retries.",
            inline_schema(SaveRegistration.model_json_schema()),
        ),
        (
            "reset_registration",
            "Discard unfinished collection when the caller starts over or cancels.",
            empty_schema,
        ),
    ]
    tools = [
        {
            "type": "function",
            "async": False,
            "function": {"name": name, "description": description, "parameters": schema},
            "server": server,
        }
        for name, description, schema in specs
    ]
    tools.append({"type": "endCall"})
    return {
        "name": "Synthetic Patient Registration",
        "firstMessage": "Hello! I'm your registration assistant. This is a demo, so please use "
        "fictional patient details only. What is the patient's first and last name?",
        "model": {
            "provider": "google",
            "model": model,
            "temperature": 0.2,
            "maxTokens": 2048,
            "messages": [
                {
                    "role": "system",
                    "content": Path(__file__).with_name("prompt.md").read_text(encoding="utf-8"),
                }
            ],
            "tools": tools,
        },
        "transcriber": {"provider": "deepgram", "model": "nova-3", "language": "en"},
        "voice": {"provider": "deepgram", "voiceId": "asteria"},
        "server": server,
        "serverMessages": ["tool-calls", "end-of-call-report", "status-update"],
        "maxDurationSeconds": 900,
        "backgroundSound": "off",
        "startSpeakingPlan": {"waitSeconds": 0.4},
        "stopSpeakingPlan": {"numWords": 2, "voiceSeconds": 0.2, "backoffSeconds": 1.0},
        "artifactPlan": {"recordingEnabled": False, "pcapEnabled": False},
    }
