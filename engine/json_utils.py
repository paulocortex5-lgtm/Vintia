"""JSON utilities: safe loads, atomic writes, JSON Schema validation (§16).

All state and artifact writes go through :func:`atomic_write_json`
(temp file + ``os.replace``) so a crash mid-write can never corrupt the
authoritative state file.

Task 1.7 adds the LLM-output helpers: :func:`strip_fences`,
:func:`canonical_json` and :func:`safe_parse`.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from typing import Any

from jsonschema import Draft202012Validator

from .errors import SchemaValidationError

# LLM responses often wrap JSON in ```json ... ``` fences (R16: we must
# tolerate them without letting them corrupt a schema-bound artifact).
_FENCE_RE = re.compile(r"^[\s\S]*?```(?:json|JSON|js)?\s*([\s\S]*?)```\s*$")


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


# ── LLM-output helpers (task 1.7) ─────────────────────────────────────────
def strip_fences(text: str) -> str:
    """Remove markdown code fences from an LLM reply.

    ``"```json\n{...}\n```"`` -> ``"{...}"``. A reply without fences is
    returned stripped, so this is safe to apply unconditionally.
    """
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def canonical_json(value: Any) -> str:
    """Deterministic JSON bytes for hashing / idempotency keys (R5).

    Keys sorted, compact separators, ``ensure_ascii=False`` so content
    hashes are stable across runs and platforms.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def safe_parse(text: str) -> Any:
    """Parse JSON, tolerating markdown fences and surrounding prose.

    Tries, in order: plain ``json.loads``, fence-stripped ``json.loads``,
    then the first balanced ``{...}`` / ``[...]`` block inside the text.
    Raises :class:`~engine.errors.SchemaValidationError` when nothing
    parses — the caller decides how to fail the task (R15/R20).
    """
    candidates = [text]
    fenced = strip_fences(text)
    if fenced != text:
        candidates.append(fenced)
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
    # Last resort: locate the first top-level JSON object/array.
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = candidate.find(open_ch) if isinstance(candidate, str) else -1
        if start == -1:
            continue
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(candidate)):
            ch = candidate[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(candidate[start : idx + 1])
                    except json.JSONDecodeError:
                        break
    raise SchemaValidationError(f"no parseable JSON found in LLM output ({len(text)} chars)")
