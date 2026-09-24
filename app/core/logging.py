import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("registration")


def configure_logging(level: str) -> None:
    logger.setLevel(level.upper())
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.propagate = False


def log_event(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"timestamp": datetime.now(UTC).isoformat(), "event": event, **fields}))
