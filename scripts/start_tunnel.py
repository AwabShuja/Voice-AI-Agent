"""Start the local development tunnel without writing authentication into global config."""

import os
import subprocess

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    domain = os.getenv("NGROK_DOMAIN", "")
    if not os.getenv("NGROK_AUTHTOKEN") or not domain:
        print("Set NGROK_AUTHTOKEN and NGROK_DOMAIN (hostname only) in .env first.")
        return 1
    if "://" in domain or "/" in domain:
        print("NGROK_DOMAIN must be a hostname without a scheme or path.")
        return 1
    try:
        return subprocess.call(["ngrok", "http", f"--url=https://{domain}", "8000"])
    except FileNotFoundError:
        print("Install ngrok and add it to PATH before running this command.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
