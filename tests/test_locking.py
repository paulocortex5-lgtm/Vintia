"""Tests for ``engine/locking.py`` — the 30-minute stealable run lock."""

import json
import time

from engine.locking import StateLock


def test_acquire_and_release(tmp_path):
    file = tmp_path / "state.lock"
    lock = StateLock(str(file))
    assert lock.acquire(owner="run-1", run_id=1)
    assert lock.is_held
    holder = json.loads(file.read_text(encoding="utf-8"))
    assert holder["owner"] == "run-1"
    assert holder["run_id"] == 1
    assert "pid" in holder
    lock.release()
    assert not lock.is_held
    assert not file.exists()


def test_second_lock_is_refused(tmp_path):
    path = str(tmp_path / "state.lock")
    first = StateLock(path)
    second = StateLock(path)
    assert first.acquire()
    assert not second.acquire()
    first.release()
    assert second.acquire()
    second.release()


def test_release_is_idempotent(tmp_path):
    file = tmp_path / "state.lock"
    lock = StateLock(str(file))
    lock.release()  # no lock held yet — must not raise
    lock.acquire()
    lock.release()
    lock.release()
    assert not file.exists()


def test_stale_lock_is_stolen(tmp_path):
    file = tmp_path / "state.lock"
    stale = {"pid": 1, "owner": "old-run", "run_id": 99, "acquired_at": time.time() - 3700}
    file.write_text(json.dumps(stale), encoding="utf-8")
    lock = StateLock(str(file), stale_after_sec=1800)
    assert lock.acquire(owner="new-run")
    holder = json.loads(file.read_text(encoding="utf-8"))
    assert holder["owner"] == "new-run"
    assert holder["run_id"] is None
    lock.release()


def test_fresh_lock_is_not_stolen_without_flag(tmp_path):
    file = tmp_path / "state.lock"
    fresh = {"pid": 1, "owner": "current-run", "run_id": 5, "acquired_at": time.time()}
    file.write_text(json.dumps(fresh), encoding="utf-8")
    lock = StateLock(str(file), stale_after_sec=1800)
    assert not lock.acquire()
    assert not lock.is_held
    assert json.loads(file.read_text(encoding="utf-8"))["owner"] == "current-run"


def test_stale_lock_reclaimed_with_explicit_steal(tmp_path):
    file = tmp_path / "state.lock"
    fresh = {"pid": 1, "owner": "zombie", "run_id": 1, "acquired_at": time.time()}
    file.write_text(json.dumps(fresh), encoding="utf-8")
    lock = StateLock(str(file))
    assert lock.acquire(steal=True, owner="rescuer")
    assert json.loads(file.read_text(encoding="utf-8"))["owner"] == "rescuer"
    lock.release()


def test_corrupt_lock_file_is_refused_not_stolen(tmp_path):
    """An unparseable lock is treated as HELD (fail-safe): acquire refuses
    and leaves the file untouched rather than destroying a lock it cannot
    interpret. Clearing it requires manually removing the file."""
    file = tmp_path / "state.lock"
    file.write_text("{not valid json", encoding="utf-8")
    lock = StateLock(str(file))
    assert lock.acquire(owner="cleaner") is False
    assert not lock.is_held
    assert file.read_text(encoding="utf-8") == "{not valid json"
    lock.release()


def test_acquire_is_idempotent_for_the_holder(tmp_path):
    path = str(tmp_path / "state.lock")
    lock = StateLock(path)
    assert lock.acquire(owner="run-1")
    assert lock.acquire(owner="run-1")
    assert lock.is_held
    lock.release()


def test_state_manager_exposes_the_lock(tmp_path):
    from engine.state_manager import VantiaState

    state = VantiaState(state_dir=str(tmp_path / ".vantia" / "state"))
    lock = state.lock()
    assert lock.path == state.lock_path
    assert lock.acquire(owner="test")
    assert not VantiaState(state_dir=str(tmp_path / ".vantia" / "state")).lock().acquire()
    lock.release()
