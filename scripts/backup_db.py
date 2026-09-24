"""Create a consistent SQLite backup, including committed WAL data."""

import argparse
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    load_dotenv()
    url = make_url(os.getenv("DATABASE_URL", "sqlite:///./data/patients.db"))
    source = Path(url.database).resolve()
    destination = args.destination or Path(".local/backups") / (
        datetime.now(UTC).strftime("patients-%Y%m%dT%H%M%S%fZ.db")
    )
    if destination.exists():
        raise SystemExit("Destination already exists; choose a new backup filename.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
        with sqlite3.connect(destination) as backup:
            original.backup(backup)
    print(f"Created consistent backup: {destination}")


if __name__ == "__main__":
    main()
