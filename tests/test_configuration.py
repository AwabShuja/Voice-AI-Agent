import json

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import AppError
from app.voice.configuration import assistant_configuration
from app.voice.state import DraftStore
from scripts import configure_vapi


def test_weak_and_reused_secrets_rejected():
    for api_key, webhook in [("short", "b" * 40), ("a" * 40, "a" * 40)]:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, api_key=api_key, vapi_webhook_secret=webhook)


def test_expired_drafts_and_capacity(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("app.voice.state.time.monotonic", lambda: clock[0])
    store = DraftStore(ttl_seconds=60, max_drafts=1)
    store.get("a").values["first_name"] = "Jane"
    with pytest.raises(AppError):
        store.get("b")
    clock[0] += 61
    assert store.get("a").values == {}


def test_assistant_configuration_contract():
    config = assistant_configuration(
        "https://example.ngrok-free.app/", "credential-id", "openai/gpt-oss-120b"
    )
    assert config["model"]["provider"] == "groq"
    assert config["transcriber"]["model"] == "nova-3"
    assert config["voice"]["voiceId"] == "asteria"
    assert config["artifactPlan"]["recordingEnabled"] is False
    tools = config["model"]["tools"]
    assert len(tools) == 5
    for tool in tools[:-1]:
        assert tool["server"]["url"] == "https://example.ngrok-free.app/vapi/webhook"
        assert tool["server"]["credentialId"] == "credential-id"
        assert "$ref" not in json.dumps(tool["function"]["parameters"])
    assert "STOP and WAIT" in config["model"]["messages"][0]["content"]


def test_provisioning_reuses_resources_and_only_free_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(configure_vapi, "STATE_PATH", tmp_path / "resources.json")
    monkeypatch.delenv("VAPI_ASSISTANT_ID", raising=False)
    monkeypatch.delenv("VAPI_PHONE_NUMBER_ID", raising=False)
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path, json.loads(request.content)))
        if request.url.path.startswith("/assistant"):
            return httpx.Response(200, json={"id": "assistant-one"})
        return httpx.Response(200, json={"id": "phone-one", "number": "+12025550143"})

    config = assistant_configuration("https://example.com", "credential-one", "openai/gpt-oss-120b")
    with httpx.Client(
        base_url="https://api.vapi.ai", transport=httpx.MockTransport(handler)
    ) as client:
        state = configure_vapi.apply_configuration(client, config, {})
        configure_vapi.apply_configuration(client, config, state)
    assert [item[:2] for item in requests] == [
        ("POST", "/assistant"),
        ("POST", "/phone-number"),
        ("PATCH", "/assistant/assistant-one"),
        ("PATCH", "/phone-number/phone-one"),
    ]
    assert requests[1][2]["provider"] == "vapi"
    assert configure_vapi.STATE_PATH.exists()


def test_provisioning_failure_retains_assistant_id(tmp_path, monkeypatch):
    monkeypatch.setattr(configure_vapi, "STATE_PATH", tmp_path / "resources.json")
    monkeypatch.delenv("VAPI_ASSISTANT_ID", raising=False)
    monkeypatch.delenv("VAPI_PHONE_NUMBER_ID", raising=False)

    def handler(request):
        if request.url.path == "/assistant":
            return httpx.Response(201, json={"id": "assistant-one"})
        return httpx.Response(400, json={"message": "No number inventory"})

    with httpx.Client(
        base_url="https://api.vapi.ai", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            configure_vapi.apply_configuration(client, {}, {})
    assert json.loads(configure_vapi.STATE_PATH.read_text())["assistant_id"] == "assistant-one"
