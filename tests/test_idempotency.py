"""Tests for ``engine/idempotency.py`` — never redo completed work."""

from engine.idempotency import IdempotencyRegistry, key


def test_key_is_stable_and_distinct():
    assert key("0.1") == key("0.1")
    assert key("0.1") != key("0.2")
    assert len(key("0.1")) == 64


def test_key_distinguishes_extra_inputs():
    assert key("0.1") != key("0.1", "resume-abc")


def test_missing_registry_reports_incomplete(tmp_path):
    registry = IdempotencyRegistry(str(tmp_path / "reg.json"))
    assert not registry.is_complete("0.3")
    assert registry.lookup("0.3") is None


def test_record_then_lookup_persists_across_instances(tmp_path):
    file = tmp_path / "reg.json"
    path = str(file)
    artifacts = ["engine/state_manager.py", "tests/test_state_manager.py"]
    IdempotencyRegistry(path).record_complete("0.3", artifacts)

    registry = IdempotencyRegistry(path)
    assert registry.is_complete("0.3")
    entry = registry.lookup("0.3")
    assert entry["task_id"] == "0.3"
    assert entry["status"] == "complete"
    assert entry["artifacts"] == artifacts
    assert entry["at"]
    assert file.exists()


def test_other_task_stays_incomplete(tmp_path):
    path = str(tmp_path / "reg.json")
    registry = IdempotencyRegistry(path)
    registry.record_complete("0.3", ["a.py"])
    assert not registry.is_complete("0.4")


def test_forget_removes_an_entry(tmp_path):
    path = str(tmp_path / "reg.json")
    registry = IdempotencyRegistry(path)
    registry.record_complete("0.3", ["a.py"])
    assert registry.forget("0.3") is True
    assert registry.is_complete("0.3") is False
    assert registry.forget("0.3") is False


def test_registry_treats_a_malformed_file_as_fatal(tmp_path):
    """A corrupt registry fails loudly on both read and write (consistent
    with state-file corruption, which resets from the seed elsewhere)
    rather than being silently treated as empty."""
    import json as _json

    file = tmp_path / "reg.json"
    path = str(file)
    file.write_text("{broken", encoding="utf-8")
    registry = IdempotencyRegistry(path)
    for call in (
        lambda: registry.is_complete("0.3"),
        lambda: registry.record_complete("0.3", ["a.py"]),
    ):
        try:
            call()
            assert False, "expected JSONDecodeError for a corrupt registry"
        except _json.JSONDecodeError:
            pass


# ── task 4.2: tamper-evident entries ─────────────────────────────────────


def _load(path: str) -> dict:
    import json

    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _dump(path: str, data: dict) -> None:
    import json

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def test_verify_is_clean_after_recording(tmp_path):
    registry = IdempotencyRegistry(str(tmp_path / "reg.json"))
    registry.record_complete("4.1", ["engine/verification/domain.py"])
    registry.record_complete("4.2", ["engine/idempotency.py"])
    ok, bad = registry.verify()
    assert ok
    assert bad == []


def test_verify_flags_a_tampered_entry(tmp_path):
    """An entry edited after recording must be reported, not trusted."""
    path = str(tmp_path / "reg.json")
    IdempotencyRegistry(path).record_complete("4.2", ["engine/idempotency.py"])

    data = _load(path)
    for entry in data.values():
        entry["artifacts"] = ["someone/else.py"]  # edited after the fact
    _dump(path, data)

    ok, bad = IdempotencyRegistry(path).verify()
    assert not ok
    assert bad == ["4.2"]


def test_verify_flags_legacy_entries_without_hashes(tmp_path):
    """Entries written before hardening are unverifiable, so reported."""
    path = str(tmp_path / "reg.json")
    _dump(
        path,
        {
            key("0.3"): {
                "task_id": "0.3",
                "status": "complete",
                "artifacts": ["engine/state_manager.py"],
                "at": "2026-09-01T00:00:00Z",
            }
        },
    )
    ok, bad = IdempotencyRegistry(path).verify()
    assert not ok
    assert bad == ["0.3"]


def test_entries_lists_all_oldest_first(tmp_path):
    registry = IdempotencyRegistry(str(tmp_path / "reg.json"))
    registry.record_complete("4.1", ["a.py"])
    registry.record_complete("4.2", ["b.py"])
    rows = registry.entries()
    assert [row["task_id"] for row in rows] == ["4.1", "4.2"]
    assert all(len(row["entry_hash"]) == 64 for row in rows)
    assert registry.entries() == registry.entries()  # stable order
