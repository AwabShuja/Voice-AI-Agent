"""Create a local environment file without printing secrets or replacing existing settings."""

import secrets
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    destination = root / ".env"
    if destination.exists():
        print(".env already exists; no changes made.")
        return
    template = (root / ".env.example").read_text(encoding="utf-8")
    template = template.replace(
        "replace-with-at-least-32-random-characters", secrets.token_urlsafe(32)
    )
    template = template.replace(
        "replace-with-a-different-32-character-secret", secrets.token_urlsafe(32)
    )
    with destination.open("x", encoding="utf-8") as file:
        file.write(template)
    print("Created .env with distinct local API and webhook secrets. Provider keys remain empty.")


if __name__ == "__main__":
    main()
