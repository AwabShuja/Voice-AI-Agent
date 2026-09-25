"""Render assistant configuration, or explicitly apply it and attach a free Vapi number."""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

from app.voice.configuration import assistant_configuration

STATE_PATH = Path(".local/vapi-resources.json")


def remember(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def require(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise ValueError(f"Set {name} in .env first")
    return value


def apply_configuration(client: httpx.Client, configuration: dict, state: dict) -> dict:
    """Persist each allocated ID immediately so retries do not recreate completed resources."""
    assistant_id = os.getenv("VAPI_ASSISTANT_ID") or state.get("assistant_id")
    if assistant_id:
        response = client.patch(f"/assistant/{assistant_id}", json=configuration)
    else:
        response = client.post("/assistant", json=configuration)
    response.raise_for_status()
    state["assistant_id"] = response.json()["id"]
    remember(state)

    number_id = os.getenv("VAPI_PHONE_NUMBER_ID") or state.get("phone_number_id")
    if number_id:
        response = client.patch(
            f"/phone-number/{number_id}", json={"assistantId": state["assistant_id"]}
        )
    else:
        # Only the free Vapi provider is supported. No paid-number or billing API is called.
        response = client.post(
            "/phone-number",
            json={
                "provider": "vapi",
                "numberDesiredAreaCode": os.getenv("VAPI_AREA_CODE", "202"),
                "name": "Patient registration demo",
                "assistantId": state["assistant_id"],
            },
        )
    response.raise_for_status()
    number = response.json()
    state.update(phone_number_id=number["id"], phone_number=number.get("number"))
    remember(state)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Create/update Vapi resources")
    args = parser.parse_args()
    load_dotenv()
    try:
        base_url = require("PUBLIC_BASE_URL")
        url = urlparse(base_url)
        if url.scheme != "https" or not url.netloc or url.path not in ("", "/"):
            raise ValueError("PUBLIC_BASE_URL must be an HTTPS origin without a path")
        configuration = assistant_configuration(
            base_url,
            require("VAPI_CREDENTIAL_ID"),
            os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        )
        destination = Path(".local/vapi-assistant.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(configuration, indent=2) + "\n", encoding="utf-8")
        print(f"Rendered {destination}. No secret values are included.")
        if not args.apply:
            print(
                "Review the file and billing prerequisites. "
                "Use --apply to provision the assistant/number."
            )
            return 0
        state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
        with httpx.Client(
            base_url="https://api.vapi.ai",
            timeout=30,
            headers={"Authorization": f"Bearer {require('VAPI_API_KEY')}"},
        ) as client:
            state = apply_configuration(client, configuration, state)
        print(f"Assistant: {state['assistant_id']}")
        print(f"Phone number: {state.get('phone_number') or 'Check Vapi provisioning status'}")
        print("Use only free credits. Verify the live phone path before marking the demo complete.")
        return 0
    except httpx.HTTPStatusError as exc:
        print(
            f"Vapi rejected {exc.request.method} {exc.request.url.path}: "
            f"HTTP {exc.response.status_code}."
        )
        print(
            "Review the Vapi dashboard; saved resource IDs are in .local/vapi-resources.json. "
            "If a request timed out after provisioning, inspect the dashboard "
            "and set its ID before retrying."
        )
    except httpx.RequestError:
        print(
            "Vapi could not be reached. "
            "Inspect the dashboard for partially created resources before retrying."
        )
    except (ValueError, KeyError) as exc:
        print(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
