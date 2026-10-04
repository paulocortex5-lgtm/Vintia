"""json_utils tests: atomic writes, fence stripping, canonical JSON, safe_parse.

Task 1.7 acceptance: LLM replies wrapped in ```json fences must be stripped
and parsed, and canonical JSON must be deterministic for idempotency keys.
"""

import hashlib

import pytest

from engine.errors import SchemaValidationError
from engine.json_utils import (
    atomic_write_json,
    canonical_json,
    load_json,
    safe_parse,
    strip_fences,
    validate,
)

# ── strip_fences ──────────────────────────────────────────────────────


def test_strip_fences_removes_markdown_fences():
    assert strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_fences('```{"a": 1}```') == '{"a": 1}'
    assert strip_fences('  {"a": 1}\n') == '{"a": 1}'


def test_strip_fences_leaves_plain_json_alone():
    payload = '{"a": [1, 2], "b": {"c": 3}}'
    assert strip_fences(payload) == payload


def test_strip_fences_only_strips_fences_at_the_ends():
    # _FENCE_RE is anchored: prose around the block is NOT modified,
    # but safe_parse's balanced-block fallback recovers the JSON.
    text = 'Here you go:\n```json\n{"a": 1}\n```\nEnjoy!'
    assert strip_fences(text) == text.strip()
    assert safe_parse(text) == {"a": 1}


# ── canonical_json ────────────────────────────────────────────────────


def test_canonical_json_is_order_independent():
    left = canonical_json({"b": 1, "a": [3, 2]})
    right = canonical_json({"a": [3, 2], "b": 1})
    assert left == right
    assert '"a":[3,2]' in left  # compact separators, sorted keys


def test_canonical_json_hashes_stably_across_argument_orders():
    payload = {"z": 1, "a": {"b": 2}}
    other = {"a": {"b": 2}, "z": 1}
    assert hashlib.sha256(canonical_json(payload).encode()).hexdigest() == (
        hashlib.sha256(canonical_json(other).encode()).hexdigest()
    )


# ── safe_parse ────────────────────────────────────────────────────────


def test_safe_parse_accepts_plain_json_objects_and_arrays():
    assert safe_parse('{"a": 1}') == {"a": 1}
    assert safe_parse("[1, 2, 3]") == [1, 2, 3]


def test_safe_parse_accepts_fenced_json():
    assert safe_parse('```json\n{"ok": true}\n```') == {"ok": True}


def test_safe_parse_recovers_json_embedded_in_prose():
    text = 'Sure! The result is {"score": 92} — hope that helps.'
    assert safe_parse(text) == {"score": 92}


def test_safe_parse_respects_quotes_inside_strings():
    text = '{"quote": "he said \\"hi\\" loudly"}'
    assert safe_parse(text) == {"quote": 'he said "hi" loudly'}


def test_safe_parse_rejects_garbage():
    with pytest.raises(SchemaValidationError, match="parseable JSON"):
        safe_parse("no json here at all")


def test_safe_parse_matches_strip_fences_output():
    fenced = '```json\n{"nested": {"x": 1}}\n```'
    assert safe_parse(fenced) == safe_parse(strip_fences(fenced))


# ── atomic_write_json / load_json ─────────────────────────────────────


def test_atomic_write_json_creates_parent_dirs_and_roundtrips(tmp_path):
    path = tmp_path / "a" / "b" / "c.json"
    payload = {"tasks": {"1.5": "complete"}, "n": 1}
    atomic_write_json(str(path), payload)
    assert path.exists()
    assert load_json(str(path)) == payload


def test_atomic_write_json_leaves_no_temp_files_behind(tmp_path):
    atomic_write_json(str(tmp_path / "data.json"), {"x": 1})
    assert list(tmp_path.glob(".tmp-*")) == []


def test_atomic_write_json_replaces_existing_content(tmp_path):
    path = tmp_path / "data.json"
    atomic_write_json(str(path), {"v": 1})
    atomic_write_json(str(path), {"v": 2})
    assert load_json(str(path)) == {"v": 2}


# ── validate ──────────────────────────────────────────────────────────


def test_validate_returns_empty_list_for_valid_input():
    schema = {
        "type": "object",
        "required": ["a", "b"],
        "properties": {"a": {"type": "integer"}, "b": {"type": "string"}},
    }
    assert validate({"a": 1, "b": "x"}, schema) == []


def test_validate_raises_and_names_every_offending_path():
    schema = {
        "type": "object",
        "required": ["a", "b", "c"],
        "properties": {"a": {"type": "integer"}, "b": {"type": "string"}},
    }
    with pytest.raises(SchemaValidationError) as excinfo:
        validate({"a": "not-an-int", "b": 5}, schema)
    assert excinfo.value.errors, "every violation must be carried on .errors"
    joined = " ".join(excinfo.value.errors)
    assert "a" in joined and "b" in joined
    assert "c" in joined  # missing required key is reported too
