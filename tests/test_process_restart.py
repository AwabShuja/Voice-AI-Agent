"""Exercise persistence through two actual Uvicorn processes and real HTTP requests."""

import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager

import httpx

from tests.conftest import ROOT, TEST_API_KEY, TEST_WEBHOOK_SECRET


@contextmanager
def running_server(settings):
    with socket.socket() as address:
        address.bind(("127.0.0.1", 0))
        port = address.getsockname()[1]
    environment = {
        **os.environ,
        "DATABASE_URL": settings.database_url,
        "API_KEY": TEST_API_KEY,
        "VAPI_WEBHOOK_SECRET": TEST_WEBHOOK_SECRET,
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=2, headers={"X-API-Key": TEST_API_KEY}
        ) as client:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                assert process.poll() is None, "Uvicorn exited before becoming ready"
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                time.sleep(0.1)
            else:
                raise AssertionError("Uvicorn did not start within 20 seconds")
            yield client
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_real_process_restart_preserves_patient(settings, patient):
    with running_server(settings) as first:
        response = first.post("/patients", json=patient)
        assert response.status_code == 201
        saved = response.json()["data"]
    with running_server(settings) as restarted:
        assert restarted.get(f"/patients/{saved['patient_id']}").json()["data"] == saved
        assert (
            restarted.post("/patients", json={**patient, "first_name": "Alex"}).status_code == 201
        )
        assert len(restarted.get("/patients").json()["data"]) == 2
