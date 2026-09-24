import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from app.core.errors import AppError
from app.schemas.patient import PatientCreate


@dataclass
class RegistrationDraft:
    values: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    prepared: PatientCreate | None = None
    confirmation_token: str | None = None
    touched_at: float = field(default_factory=time.monotonic)


class DraftStore:
    """Bounded, process-local drafts. Run one worker; completed receipts live in SQLite."""

    def __init__(self, ttl_seconds: int, max_drafts: int):
        self.ttl_seconds = ttl_seconds
        self.max_drafts = max_drafts
        self.drafts: dict[str, RegistrationDraft] = {}
        # Tool operations are short and serialized so a correction cannot race a commit.
        self.lock = RLock()

    def get(self, call_id: str) -> RegistrationDraft:
        now = time.monotonic()
        expired = [
            key for key, draft in self.drafts.items() if now - draft.touched_at > self.ttl_seconds
        ]
        for key in expired:
            del self.drafts[key]
        if call_id not in self.drafts:
            if len(self.drafts) >= self.max_drafts:
                raise AppError(503, "capacity_exceeded", "Please try registration again shortly.")
            self.drafts[call_id] = RegistrationDraft()
        self.drafts[call_id].touched_at = now
        return self.drafts[call_id]

    def discard(self, call_id: str) -> RegistrationDraft | None:
        with self.lock:
            return self.drafts.pop(call_id, None)
