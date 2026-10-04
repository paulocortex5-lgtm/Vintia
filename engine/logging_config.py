"""Structured JSON logging (§6.1).

Every line on stdout is one JSON object::

    {"ts": "2026-10-03T22:00:00.123456+00:00", "level": "INFO",
     "logger": "vantia.cost", "run_id": "a1b2c3d4e5f6", "msg": "...",
     "data": {"task_id": "0.3", "usd": 0.0}}

``data`` is optional and carries structured fields (task ids, hashes,
provider, tokens). Machine-readable output makes every LLM call and
artifact write auditable (§0).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import UTC, datetime

_RUN_ID: str | None = None


def get_run_id() -> str:
    """Return the active run id, generating one if none is set."""
    global _RUN_ID
    if _RUN_ID is None:
        _RUN_ID = os.environ.get("VANTIA_RUN_ID") or uuid.uuid4().hex[:12]
    return _RUN_ID


def utc_now() -> str:
    """Current UTC time as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class JsonLineFormatter(logging.Formatter):
    """Render every log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "run_id": getattr(record, "run_id", None) or _RUN_ID,
            "msg": record.getMessage(),
        }
        data = getattr(record, "data", None)
        if data:
            entry["data"] = data
        if record.exc_info and record.exc_info[0] is not None:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str | int = "INFO", *, run_id: str | None = None) -> None:
    """Install a single JSON-line handler on the root logger."""
    global _RUN_ID
    if run_id:
        _RUN_ID = run_id
    root = logging.getLogger()
    root.setLevel(
        level if isinstance(level, int) else getattr(logging, str(level).upper(), logging.INFO)
    )
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLineFormatter())
    root.addHandler(handler)


def log_data(logger: logging.Logger, level: int, msg: str, **data: object) -> None:
    """Emit ``msg`` at ``level`` with ``data`` attached as a JSON object."""
    frame = sys._getframe(2)
    record = logger.makeRecord(
        logger.name, level, frame.f_code.co_filename, frame.f_lineno, msg, (), None
    )
    record.data = data
    record.run_id = _RUN_ID
    logger.handle(record)
