"""Read-only checks of a running local or deployed API. Never print keys or records."""

import argparse
import os

import httpx
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    key = os.getenv("API_KEY")
    if not key:
        print("Set API_KEY in .env before checking the patient endpoints.")
        return 1
    try:
        with httpx.Client(
            base_url=args.base_url.rstrip("/"),
            timeout=15,
            headers={"ngrok-skip-browser-warning": "true"},
        ) as client:
            health = client.get("/health")
            health.raise_for_status()
            if health.json()["data"]["status"] != "ok":
                raise ValueError("Health endpoint is not ready")
            print("Health: OK")
            documentation = client.get("/docs")
            documentation.raise_for_status()
            print("Swagger documentation: OK")
            patients = client.get("/patients", headers={"X-API-Key": key})
            patients.raise_for_status()
            records = patients.json()["data"]
            if not isinstance(records, list):
                raise ValueError("Unexpected patient response envelope")
            print(f"Authenticated patient API: OK ({len(records)} active records)")
            if client.get("/patients").status_code != 401:
                raise ValueError("Patient API did not reject an unauthenticated request")
            print("Unauthenticated access rejected: OK")
        return 0
    except httpx.HTTPStatusError as exc:
        print(f"API check failed: HTTP {exc.response.status_code}; verify URL and API_KEY.")
    except httpx.RequestError:
        print("API could not be reached; start the server/tunnel and verify the URL.")
    except (ValueError, KeyError, TypeError):
        print("API returned an unexpected response; verify that the URL reaches this application.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
