"""Application tracker tests (task 15.8 §12.4).

Offline: each test isolates ``$VANTIA_APPLICATIONS_DIR`` to ``tmp_path`` via
monkeypatch. Covers create/idempotency, snapshotting, status validation,
owner isolation, kanban counts, update and delete.
"""

import pytest

from engine.applications import tracker


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_APPLICATIONS_DIR", str(tmp_path / "apps"))
    return tracker


@pytest.fixture()
def t(tmp_path, monkeypatch):
    return _isolate(tmp_path, monkeypatch)


def _job(job_id, **over):
    base = {
        "id": job_id,
        "title": "Senior Backend Engineer",
        "company": "Acme",
        "country": "GB",
        "location": "London",
        "apply_url": f"https://acme.example.com/apply/{job_id}",
        "link_status": "verified",
        "posted_at": "2026-10-10",
    }
    base.update(over)
    return base


def test_status_vocabulary_is_fixed():
    assert tracker.APPLICATION_STATUSES == (
        "applied",
        "interview",
        "offer",
        "rejected",
        "withdrawn",
    )


def test_create_snapshots_job(t):
    row = t.create_application("u1", "job-1", job=_job("job-1"))
    assert row["status"] == "applied"
    assert row["job_snapshot"]["title"] == "Senior Backend Engineer"
    assert row["job_snapshot"]["apply_url"].startswith("https://")
    assert row["applied_at"] and row["updated_at"]


def test_create_is_idempotent_per_user_and_job(t):
    first = t.create_application("u1", "job-1", job=_job("job-1"))
    second = t.create_application("u1", "job-1", job=_job("job-1"))
    assert first["id"] == second["id"]
    assert len(t.applications_for("u1")) == 1


def test_same_job_different_users_are_separate(t):
    a = t.create_application("u1", "job-1", job=_job("job-1"))
    b = t.create_application("u2", "job-1", job=_job("job-1"))
    assert a["id"] != b["id"]


def test_owner_isolation(t):
    t.create_application("u1", "job-1", job=_job("job-1"))
    t.create_application("u1", "job-2", job=_job("job-2"))
    t.create_application("u2", "job-3", job=_job("job-3"))
    assert len(t.applications_for("u1")) == 2
    assert len(t.applications_for("u2")) == 1
    assert len(t.applications_for("u3")) == 0


def test_snapshot_survives_source_removal(t):
    # Snapshot the job, then "remove" it — the card still holds its fields.
    t.create_application("u1", "job-1", job=_job("job-1", title="Legacy Role"))
    card = t.applications_for("u1")[0]
    assert card["job_snapshot"]["title"] == "Legacy Role"


def test_invalid_status_refused(t):
    with pytest.raises(tracker.VantiaError) as exc:
        t.create_application("u1", "job-1", job=_job("job-1"), status="ghosted")
    assert exc.value.code == "invalid_status"


def test_update_moves_column_and_counts(t):
    row = t.create_application("u1", "job-1", job=_job("job-1"))
    t.create_application("u1", "job-2", job=_job("job-2"))
    updated = t.update_application("u1", row["id"], status="interview")
    assert updated["status"] == "interview"
    counts = t.counts_for("u1")
    assert counts["applied"] == 1
    assert counts["interview"] == 1
    assert counts["total"] == 2


def test_update_cannot_touch_other_users_card(t):
    row = t.create_application("u1", "job-1", job=_job("job-1"))
    with pytest.raises(tracker.VantiaError) as exc:
        t.update_application("u2", row["id"], status="offer")
    assert exc.value.code == "application_not_found"


def test_delete_removes_owned_card(t):
    row = t.create_application("u1", "job-1", job=_job("job-1"))
    assert t.delete_application("u1", row["id"]) is True
    assert t.applications_for("u1") == []


def test_delete_other_users_card_refused(t):
    row = t.create_application("u1", "job-1", job=_job("job-1"))
    with pytest.raises(tracker.VantiaError) as exc:
        t.delete_application("u2", row["id"])
    assert exc.value.code == "application_not_found"
    assert len(t.applications_for("u1")) == 1


def test_list_filters_by_status(t):
    a = t.create_application("u1", "job-1", job=_job("job-1"))
    t.create_application("u1", "job-2", job=_job("job-2"))
    t.update_application("u1", a["id"], status="rejected")
    rejected = t.list_applications("u1", status="rejected")
    assert [r["id"] for r in rejected] == [a["id"]]


def test_missing_ids_refused(t):
    with pytest.raises(tracker.VantiaError):
        t.create_application("", "job-1", job=_job("job-1"))
    with pytest.raises(tracker.VantiaError):
        t.create_application("u1", "", job=_job(""))
