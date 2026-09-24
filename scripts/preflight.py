"""Check readiness without creating resources, placing calls, or printing credentials."""

import argparse
import os
import shutil
from pathlib import Path

import httpx
from dotenv import load_dotenv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online", action="store_true", help="Also check Groq and Vapi API access")
    args = parser.parse_args()
    load_dotenv()
    missing = []
    for name in (
        "API_KEY",
        "VAPI_WEBHOOK_SECRET",
        "VAPI_API_KEY",
        "GROQ_API_KEY",
        "VAPI_CREDENTIAL_ID",
        "PUBLIC_BASE_URL",
        "NGROK_AUTHTOKEN",
        "NGROK_DOMAIN",
    ):
        present = bool(os.getenv(name))
        print(f"{name}: {'SET' if present else 'MISSING'}")
        if not present:
            missing.append(name)
    for executable in ("docker", "ngrok", "aws", "gh"):
        print(f"{executable} CLI: {'available' if shutil.which(executable) else 'not installed'}")
    aws_configured = (
        bool(os.getenv("AWS_PROFILE") or os.getenv("AWS_ACCESS_KEY_ID"))
        or (Path.home() / ".aws" / "credentials").exists()
    )
    aws_status = "present (not verified)" if aws_configured else "not found"
    print(f"AWS credential configuration: {aws_status}")

    failed = False
    if args.online:
        endpoints = [
            ("Groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1/models"),
            ("Vapi", "VAPI_API_KEY", "https://api.vapi.ai/assistant?limit=1"),
        ]
        with httpx.Client(timeout=20) as client:
            for provider, env_name, url in endpoints:
                key = os.getenv(env_name)
                if not key:
                    continue
                try:
                    response = client.get(url, headers={"Authorization": f"Bearer {key}"})
                    response.raise_for_status()
                    if provider == "Groq":
                        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
                        available = {item["id"] for item in response.json()["data"]}
                        if model not in available:
                            print("Groq: configured model is unavailable to this account")
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
        "Manual checks: AWS credit expiry, Vapi free balance/auto-reload OFF, review window, "
        "and U.S. phone reachability. This command never purchases or provisions anything."
    )
    return 1 if missing or failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
