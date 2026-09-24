import json
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import create_app
from app.models import Patient, RegistrationReceipt
from tests.conftest import TEST_API_KEY, TEST_WEBHOOK_SECRET


def result(response):
    assert "result" in response, response
    return json.loads(response["result"])


def error(response):
    assert "error" in response, response
    return json.loads(response["error"])


def prepare(tool, payload, call_id="provider-call-1"):
    updated = result(tool("update_registration", {"fields": payload}, call_id=call_id))
    assert updated["missing_fields"] == []
    return result(tool("prepare_registration", call_id=call_id))


def test_registration_full_readback_and_commit(tool, all_fields, client):
    prepared = prepare(tool, all_fields)
    assert prepared["status"] == "awaiting_confirmation"
    for value in all_fields.values():
        assert value in prepared["readback"]
    assert client.get("/patients").json()["data"] == []
    saved = result(
        tool(
            "save_registration",
            {
                "confirmation_token": prepared["confirmation_token"],
                "caller_confirmed": True,
            },
        )
    )
    assert saved["status"] == "saved"
    assert saved["patient"]["first_name"] == "Jane"
    assert client.get(f"/patients/{saved['patient']['patient_id']}").status_code == 200


def test_optional_defaults_and_nulls(tool, patient):
    prepared = prepare(tool, patient)
    assert "Preferred language: English" in prepared["readback"]
    assert "Email:" not in prepared["readback"]
    assert "None" not in prepared["readback"]


def test_invalid_field_correction_and_out_of_order(tool, patient):
    update = result(
        tool("update_registration", {"fields": {"city": "Boston", "phone_number": "123"}})
    )
    assert update["collected"] == {"city": "Boston"}
    assert "phone_number" in update["errors"]
    assert error(tool("prepare_registration"))["code"] == "invalid_draft"
    prepare(tool, patient)
    update = result(tool("update_registration", {"fields": {"date_of_birth": "02/30/2000"}}))
    assert "date_of_birth" not in update["collected"]
    assert "date_of_birth" in update["errors"]
    assert error(tool("prepare_registration"))["code"] == "invalid_draft"
    result(tool("update_registration", {"fields": {"date_of_birth": "02/29/2000"}}))
    assert result(tool("prepare_registration"))["status"] == "awaiting_confirmation"


def test_correction_invalidates_confirmation(tool, patient, client):
    original = prepare(tool, patient)
    result(tool("update_registration", {"fields": {"last_name": "Smith"}}))
    args = {"confirmation_token": original["confirmation_token"], "caller_confirmed": True}
    assert error(tool("save_registration", args))["code"] == "not_prepared"
    current = result(tool("prepare_registration"))
    assert error(tool("save_registration", args))["code"] == "stale_confirmation"
    assert client.get("/patients").json()["data"] == []
    args["confirmation_token"] = current["confirmation_token"]
    assert result(tool("save_registration", args))["patient"]["last_name"] == "Smith"


def test_unconfirmed_missing_data_reset_and_isolation(tool, patient, client):
    args = {"confirmation_token": "x" * 43, "caller_confirmed": True}
    assert error(tool("save_registration", args))["code"] == "not_prepared"
    assert error(tool("prepare_registration"))["code"] == "validation_error"
    prepared = prepare(tool, patient)
    args["confirmation_token"] = prepared["confirmation_token"]
    args["caller_confirmed"] = False
    assert error(tool("save_registration", args))["code"] == "confirmation_required"
    args["caller_confirmed"] = "yes"
    assert error(tool("save_registration", args))["code"] == "validation_error"
    args["caller_confirmed"] = True
    assert error(tool("save_registration", args, call_id="other-call"))["code"] == "not_prepared"
    result(tool("reset_registration"))
    assert error(tool("save_registration", args))["code"] == "not_prepared"
    assert client.get("/patients").json()["data"] == []


def test_dropped_call_and_no_end_report_write(tool, patient, client):
    prepare(tool, patient)
    response = client.post(
        "/vapi/webhook",
        headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
        json={
            "message": {
                "type": "end-of-call-report",
                "call": {"id": "provider-call-1"},
                "artifact": {"messages": [], "structuredData": patient},
            },
        },
    )
    assert response.status_code == 200
    assert client.get("/patients").json()["data"] == []
    assert error(tool("prepare_registration"))["code"] == "validation_error"


def test_repeat_save_concurrently_and_after_restart(tool, patient, client, settings):
    prepared = prepare(tool, patient)
    args = {"confirmation_token": prepared["confirmation_token"], "caller_confirmed": True}
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: result(tool("save_registration", args)), range(2)))
    assert len({item["patient"]["patient_id"] for item in responses}) == 1
    assert len(client.get("/patients").json()["data"]) == 1
    with TestClient(create_app(settings)) as restarted:
        response = restarted.post(
            "/vapi/webhook",
            headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
            json={
                "message": {
                    "type": "tool-calls",
                    "call": {"id": "provider-call-1"},
                    "toolCallList": [
                        {
                            "id": "retry-after-restart",
                            "function": {"name": "save_registration", "arguments": args},
                        }
                    ],
                },
            },
        )
        replay = result(response.json()["results"][0])
        assert replay["repeated_request"] is True
        assert replay["patient"]["patient_id"] == responses[0]["patient"]["patient_id"]
        assert (
            len(restarted.get("/patients", headers={"X-API-Key": TEST_API_KEY}).json()["data"]) == 1
        )


def test_atomic_rollback_and_retry(tool, patient, app):
    prepared = prepare(tool, patient)
    args = {"confirmation_token": prepared["confirmation_token"], "caller_confirmed": True}
    from sqlalchemy import event

    session_class = app.state.session_factory.class_

    def fail_receipt(session, context, instances):
        if any(isinstance(item, RegistrationReceipt) for item in session.new):
            raise RuntimeError("simulated receipt write failure")

    event.listen(session_class, "before_flush", fail_receipt)
    try:
        assert error(tool("save_registration", args))["code"] == "save_unavailable"
    finally:
        event.remove(session_class, "before_flush", fail_receipt)
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Patient)) == 0
        assert session.scalar(select(func.count()).select_from(RegistrationReceipt)) == 0
    assert result(tool("save_registration", args))["status"] == "saved"


def test_tool_protocol_and_auth(tool, client, patient):
    assert client.post("/vapi/webhook", json={"message": {}}).status_code == 401
    assert error(tool("unknown_tool"))["code"] == "unknown_tool"
    assert (
        error(tool("update_registration", {"fields": {"patient_id": "malicious"}}))["code"]
        == "unknown_fields"
    )
    assert (
        result(tool("update_registration", {"fields": patient}, variant="direct"))["missing_fields"]
        == []
    )
    response = client.post(
        "/vapi/webhook",
        headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
        json={
            "message": {
                "type": "tool-calls",
                "call": {"id": "json-arguments-call"},
                "toolCallList": [
                    {
                        "id": "first",
                        "function": {
                            "name": "update_registration",
                            "arguments": json.dumps({"fields": patient}),
                        },
                    },
                    {
                        "id": "second",
                        "function": {"name": "prepare_registration", "arguments": "{"},
                    },
                ],
            },
        },
    )
    assert response.status_code == 200
    assert [item["toolCallId"] for item in response.json()["results"]] == ["first", "second"]
    assert "result" in response.json()["results"][0]
    assert "error" in response.json()["results"][1]
