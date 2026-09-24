from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
TEST_API_KEY = "test-api-" + "a" * 40
TEST_WEBHOOK_SECRET = "test-webhook-" + "b" * 40


def migrate(database_url: str) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")


@pytest.fixture
def settings(tmp_path):
    result = Settings(
        _env_file=None,
        api_key=TEST_API_KEY,
        vapi_webhook_secret=TEST_WEBHOOK_SECRET,
        database_url=f"sqlite:///{(tmp_path / 'patients.db').as_posix()}",
    )
    migrate(result.database_url)
    return result


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers["X-API-Key"] = TEST_API_KEY
        yield test_client


@pytest.fixture
def patient():
    return {
        "first_name": "Jane",
        "last_name": "O'Neil",
        "date_of_birth": "02/29/2000",
        "sex": "Female",
        "phone_number": "2025550143",
        "address_line_1": "123 Example Street",
        "city": "Boston",
        "state": "MA",
        "zip_code": "02108",
    }


@pytest.fixture
def all_fields(patient):
    return {
        **patient,
        "email": "jane@example.com",
        "address_line_2": "Unit 4",
        "insurance_provider": "Example Insurance",
        "insurance_member_id": "ABC1234",
        "preferred_language": "English",
        "emergency_contact_name": "Alex Example",
        "emergency_contact_phone": "2025550198",
    }


@pytest.fixture
def tool(client):
    def invoke(
        name, arguments=None, call_id="provider-call-1", tool_id="tool-1", variant="function"
    ):
        function = {"name": name, "arguments": arguments or {}}
        item = {"id": tool_id, "function": function}
        if variant == "direct":
            item = {"id": tool_id, "name": name, "parameters": arguments or {}}
        response = client.post(
            "/vapi/webhook",
            headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
            json={
                "message": {"type": "tool-calls", "call": {"id": call_id}, "toolCallList": [item]}
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()["results"][0]
        assert result["toolCallId"] == tool_id
        return result

    return invoke
