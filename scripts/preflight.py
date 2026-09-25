"""Check readiness without creating resources, placing calls, or printing credentials."""

import argparse
import os
import shutil

import httpx
from dotenv import load_dotenv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--online", action="store_true", help="Also check Gemini and Vapi API access"
    )
    args = parser.parse_args()
    load_dotenv()
    missing = []
    for name in (
        "API_KEY",
        "VAPI_WEBHOOK_SECRET",
        "VAPI_API_KEY",
        "GEMINI_API_KEY",
        "VAPI_CREDENTIAL_ID",
        "PUBLIC_BASE_URL",
        "NGROK_AUTHTOKEN",
        "NGROK_DOMAIN",
    ):
        present = bool(os.getenv(name))
        print(f"{name}: {'SET' if present else 'MISSING'}")
        if not present:
            missing.append(name)
    if "GEMINI_API_KEY" in missing and os.getenv("GROQ_API_KEY"):
        print(
            "Legacy Groq settings detected: replace GROQ_API_KEY/GROQ_MODEL with "
            "GEMINI_API_KEY/GEMINI_MODEL in .env."
        )
    for executable in ("docker", "ngrok", "az", "gh"):
        print(f"{executable} CLI: {'available' if shutil.which(executable) else 'not installed'}")
    print("Azure application credentials: not required (deploy through the portal or Cloud Shell)")

    failed = False
    if args.online:
        endpoints = [
            (
                "Gemini",
                "GEMINI_API_KEY",
                "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
            ),
            ("Vapi", "VAPI_API_KEY", "https://api.vapi.ai/assistant?limit=1"),
        ]
        with httpx.Client(timeout=20) as client:
            for provider, env_name, url in endpoints:
                key = os.getenv(env_name)
                if not key:
                    continue
                try:
                    headers = (
                        {"x-goog-api-key": key}
                        if provider == "Gemini"
                        else {"Authorization": f"Bearer {key}"}
                    )
                    response = client.get(url, headers=headers)
                    response.raise_for_status()
                    if provider == "Gemini":
                        model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
                        available = {
                            item["name"].removeprefix("models/")
                            for item in response.json().get("models", [])
                        }
                        if model not in available:
                            print("Gemini: configured model is unavailable to this account")
                            failed = True
                            continue
                    print(f"{provider}: API access verified")
                except (httpx.HTTPError, ValueError, KeyError):
                    failed = True
                    print(
                        f"{provider}: access check failed; "
                        "verify credentials/connectivity privately"
                    )
    print(
        "Manual checks: Azure student credit/expiry and B-series quota, Vapi free balance/"
        "auto-reload OFF, review window, and U.S. phone reachability. "
        "This command never purchases or provisions anything."
    )
    return 1 if missing or failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
