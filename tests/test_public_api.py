"""Public API key + rate-limit tests (task 15.12 §16.6).

Offline: ``$VANTIA_API_KEYS_DIR`` isolated to ``tmp_path``. Covers
hash-only storage, key resolution, unique ids, delete, tier rate limits
and the sliding-window limiter (allow then 429, then recover).
"""

import pytest

from engine.public_api import keys


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_API_KEYS_DIR", str(tmp_path / "api_keys"))
    keys._rate_hits.clear()
    yield
    keys._rate_hits.clear()


def test_create_returns_raw_key_once_and_stores_hash_only():
    created = keys.create_key("uni@example.edu", name="Test", tier="free")
    raw = created["key"]
    assert raw.startswith(keys.KEY_PREFIX)
    record = created["record"]
    assert "key_hash" not in record  # never returned in the record
    # The store holds only the hash.
    stored = keys._load_all()["keys"][keys.hash_key(raw)]
    assert stored["key_hash"] == keys.hash_key(raw)
    assert keys.hash_key(raw) != raw


def test_resolve_key_roundtrip():
    created = keys.create_key("uni@example.edu")
    raw = created["key"]
    assert keys.resolve_key(raw) is not None
    assert keys.resolve_key(keys.KEY_PREFIX + "wrong") is None
    assert keys.resolve_key("") is None


def test_rate_limits_by_tier():
    assert keys.rate_limit_for("free") == 10
    assert keys.rate_limit_for("business") == 100
    assert keys.rate_limit_for("unknown") == 10  # safe default


def test_window_allows_then_blocks():
    kh = "testhash"
    for _ in range(10):
        allowed, meta = keys.window_allowance(kh, 10, now=1000.0)
        assert allowed
    blocked, meta = keys.window_allowance(kh, 10, now=1000.5)
    assert not blocked
    assert meta["remaining"] == 0
    assert meta["reset"] >= 1


def test_window_recovers_after_sixty_seconds():
    kh = "testhash2"
    for _ in range(10):
        keys.window_allowance(kh, 10, now=1000.0)
    blocked, _ = keys.window_allowance(kh, 10, now=1005.0)
    assert not blocked
    allowed, meta = keys.window_allowance(kh, 10, now=1061.0)
    assert allowed
    # Old hits (t=1000) pruned; only this new hit counts → 9 remaining.
    assert meta["remaining"] == 9


def test_list_keys_redacts_hashes():
    keys.create_key("a@example.edu")
    keys.create_key("b@example.edu")
    listed = keys.list_keys()
    assert len(listed) == 2
    assert all("key_hash" not in k for k in listed)


def test_delete_key():
    created = keys.create_key("uni@example.edu")
    key_id = created["record"]["id"]
    assert keys.delete_key(key_id) is True
    with pytest.raises(keys.VantiaError) as exc:
        keys.delete_key(key_id)
    assert exc.value.code == "api_key_not_found"


def test_owner_email_required():
    with pytest.raises(keys.VantiaError):
        keys.create_key("")
