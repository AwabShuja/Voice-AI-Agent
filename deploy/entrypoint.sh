#!/bin/sh
set -eu
# Migrate the mounted SQLite file; never recreate it on startup.
alembic upgrade head
exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --workers 1
