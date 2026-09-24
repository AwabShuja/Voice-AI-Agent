from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import Patient
from app.services import patients
from tests.conftest import TEST_API_KEY, migrate


def test_create_all_fields(client, all_fields):
    response = client.post("/patients", json=all_fields)
    assert response.status_code == 201
    body = response.json()
    assert body["error"] is None
    record = body["data"]
    assert UUID(record["patient_id"])
    assert record.items() >= all_fields.items()
    assert datetime.fromisoformat(record["created_at"]).utcoffset() == timedelta(0)
    assert record["created_at"] <= record["updated_at"]
    assert record["deleted_at"] is None
    assert client.get(f"/patients/{record['patient_id']}").json()["data"] == record


def test_required_only_and_normalization(client, patient):
    patient.update(first_name=" Jane ", state="ma", phone_number="+1 (202) 555-0143")
    response = client.post("/patients", json=patient)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["first_name"] == "Jane"
    assert data["phone_number"] == "2025550143"
    assert data["state"] == "MA"
    assert data["preferred_language"] == "English"
    assert data["email"] is None
    assert data["zip_code"] == "02108"


@pytest.mark.parametrize(
    "field,value",
    [
        ("first_name", ""),
        ("first_name", "A" * 51),
        ("last_name", "O'Neil3"),
        ("first_name", "---"),
        ("date_of_birth", "02/29/2001"),
        ("date_of_birth", "2000-02-29"),
        ("date_of_birth", "2/29/2000"),
        ("date_of_birth", (datetime.now(UTC) + timedelta(days=1)).strftime("%m/%d/%Y")),
        ("date_of_birth", None),
        ("sex", "Unknown"),
        ("phone_number", "123"),
        ("phone_number", "4165550143"),
        ("phone_number", "0005550143"),
        ("phone_number", "2025550143extension1"),
        ("phone_number", 2025550143),
        ("email", "not-email"),
        ("address_line_1", "  "),
        ("city", "A" * 101),
        ("state", "ZZ"),
        ("state", "California"),
        ("zip_code", "1234"),
        ("zip_code", "12345-123"),
        ("zip_code", 2108),
        ("insurance_member_id", "ABC-123"),
        ("emergency_contact_phone", "555"),
        ("patient_id", str(uuid4())),
        ("deleted_at", "2020-01-01"),
    ],
)
def test_invalid_fields(client, patient, field, value):
    response = client.post("/patients", json={**patient, field: value})
    assert response.status_code == 422
    assert response.json()["data"] is None
    assert response.json()["error"]["details"]
    assert client.get("/patients").json()["data"] == []


def test_required_fields(client, patient):
    for field in patient:
        incomplete = {key: value for key, value in patient.items() if key != field}
        assert client.post("/patients", json=incomplete).status_code == 422


def test_names_enum_dc_zip4(client, patient):
    for sex in ["Male", "Female", "Other", "Decline to Answer"]:
        response = client.post(
            "/patients",
            json={
                **patient,
                "first_name": "Anne-Marie",
                "last_name": "García",
                "state": "DC",
                "zip_code": "20001-1234",
                "sex": sex,
            },
        )
        assert response.status_code == 201


def test_filters(client, patient):
    first = client.post("/patients", json=patient).json()["data"]
    client.post(
        "/patients",
        json={
            **patient,
            "last_name": "Smith",
            "date_of_birth": "01/01/1990",
            "phone_number": "2025550198",
        },
    )
    for params in [
        {"last_name": "o'neil"},
        {"date_of_birth": "02/29/2000"},
        {"phone_number": "+1 (202) 555-0143"},
        {"last_name": "O'Neil", "date_of_birth": "02/29/2000", "phone_number": "2025550143"},
    ]:
        result = client.get("/patients", params=params)
        assert result.status_code == 200
        assert [record["patient_id"] for record in result.json()["data"]] == [first["patient_id"]]
    assert (
        client.get(
            "/patients", params={"last_name": "O'Neil", "phone_number": "2025550198"}
        ).json()["data"]
        == []
    )
    assert len(client.get("/patients").json()["data"]) == 2
    assert client.get("/patients", params={"date_of_birth": "not-a-date"}).status_code == 422
    assert client.get("/patients", params={"phone_number": "123"}).status_code == 422


def test_partial_update(client, all_fields):
    original = client.post("/patients", json=all_fields).json()["data"]
    url = f"/patients/{original['patient_id']}"
    result = client.put(url, json={"last_name": "Smith", "email": None}).json()["data"]
    assert result["last_name"] == "Smith"
    assert result["email"] is None
    assert result["first_name"] == original["first_name"]
    assert result["created_at"] == original["created_at"]
    assert result["updated_at"] > original["updated_at"]
    assert client.put(url, json={}).status_code == 400
    assert client.put(url, json={"first_name": None}).status_code == 422
    assert client.put(url, json={"sex": "Wrong"}).status_code == 422
    assert client.put(url, json={"patient_id": str(uuid4())}).status_code == 422


def test_optional_fields_clear(client, all_fields):
    record = client.post("/patients", json=all_fields).json()["data"]
    optional = {
        key: None
        for key in (
            "email",
            "address_line_2",
            "insurance_provider",
            "insurance_member_id",
            "preferred_language",
            "emergency_contact_name",
            "emergency_contact_phone",
        )
    }
    response = client.put(f"/patients/{record['patient_id']}", json=optional)
    assert response.status_code == 200
    assert all(response.json()["data"][key] is None for key in optional)


def test_soft_delete(client, patient, app):
    record = client.post("/patients", json=patient).json()["data"]
    url = f"/patients/{record['patient_id']}"
    result = client.delete(url)
    assert result.status_code == 200
    assert result.json()["data"]["deleted_at"]
    assert client.get(url).status_code == 404
    assert client.put(url, json={"city": "New York"}).status_code == 404
    assert client.delete(url).status_code == 404
    assert (
        client.get("/patients", params={"phone_number": patient["phone_number"]}).json()["data"]
        == []
    )
    with app.state.session_factory() as session:
        stored = session.get(Patient, record["patient_id"])
        assert stored is not None and stored.deleted_at is not None


def test_missing_records_and_bad_uuid(client, patient):
    url = f"/patients/{uuid4()}"
    assert client.get(url).status_code == 404
    assert client.put(url, json={"city": "Boston"}).status_code == 404
    assert client.delete(url).status_code == 404
    assert client.get("/patients/invalid-uuid").status_code == 422


def test_auth_and_errors(client, patient, monkeypatch):
    assert client.get("/health").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    for method, path, kwargs in [
        ("get", "/patients", {}),
        ("post", "/patients", {"json": patient}),
        ("put", f"/patients/{uuid4()}", {"json": {"city": "Boston"}}),
        ("delete", f"/patients/{uuid4()}", {}),
    ]:
        assert (
            getattr(client, method)(path, headers={"X-API-Key": "wrong"}, **kwargs).status_code
            == 401
        )
    assert (
        client.post(
            "/patients", content="{", headers={"Content-Type": "application/json"}
        ).status_code
        == 400
    )
    assert client.get("/missing").json()["error"] is not None

    def fail(*args, **kwargs):
        raise RuntimeError("private implementation information")

    monkeypatch.setattr(patients, "list_patients", fail)
    result = client.get("/patients")
    assert result.status_code == 500
    assert result.json()["error"]["code"] == "internal_error"
    assert "private implementation" not in result.text


def test_reopen_database_and_repeat_migration(settings, patient):
    with TestClient(create_app(settings)) as first:
        record = first.post("/patients", json=patient, headers={"X-API-Key": TEST_API_KEY}).json()[
            "data"
        ]
    migrate(settings.database_url)
    with TestClient(create_app(settings)) as restarted:
        response = restarted.get(
            f"/patients/{record['patient_id']}", headers={"X-API-Key": TEST_API_KEY}
        )
        assert response.status_code == 200
        assert response.json()["data"] == record


def test_database_constraints(app):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    with app.state.engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("INSERT INTO patients (patient_id) VALUES ('invalid')"))
    with app.state.session_factory() as session:
        assert list(session.scalars(select(Patient))) == []
