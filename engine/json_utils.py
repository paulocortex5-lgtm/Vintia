"""JSON utilities: safe loads, atomic writes, JSON Schema validation (§16).

All state and artifact writes go through :func:`atomic_write_json`
(temp file + ``os.replace``) so a crash mid-write can never corrupt the
authoritative state file.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

from jsonschema import Draft202012Validator

from .errors import SchemaValidationError


def load_json(path: str, default: Any = None) -> Any:
    """Load JSON from ``path``; return ``default`` if the file is absent."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def atomic_write_json(path: str, data: Any) -> None:
    """Write ``data`` as pretty-printed JSON via temp file + os.replace()."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def validate(instance: Any, schema: dict[str, Any]) -> list[str]:
    """Validate ``instance`` against a draft 2020-12 schema.

    Returns an empty list when valid. Raises
    :class:`~engine.errors.SchemaValidationError` otherwise.
    """
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    messages = [
        f"{'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in errors
    ]
    if messages:
        raise SchemaValidationError(
            f"{len(messages)} schema violation(s); first: {messages[0]}", errors=messages
        )
    return messages
