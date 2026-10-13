"""Job alert subscription tests (task 15.9 §13.5).

Offline: ``$VANTIA_ALERTS_DIR`` + ``$VANTIA_INGEST_DIR`` isolated to
``tmp_path``. Covers create/frequency validation, filter matching, digest
windows, no-duplicate suppression, owner isolation and delete.
"""

from datetime import UTC, datetime, timedelta

import pytest

from engine.alerts import manager
from engine.alerts.send_digests import DIGEST_LIMIT, build_digest, run, send_one
from engine.sources import ingest_store as store


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_ALERTS_DIR", str(tmp_path / "alerts"))
    monkeypatch.setenv("VANTIA_INGEST_DIR", str(tmp_path / "ingest"))
    return manager


def _job(external_id, title, *, country="GB", days_old=1, sponsorship=True):
    posted = (datetime.now(UTC) - timedelta(days=days_old)).strftime("%Y-%m-%d")
    return store.JobRecord(
        portal="greenhouse",
        external_id=external_id,
        title=title,
        company="Acme",
        url=f"https://acme.example.com/{external_id}",
        country=country,
        posted_at=posted,
        visa_sponsorship=sponsorship,
        link_status=store.LINK_STATUS_VERIFIED,
    )


def _seed_jobs():
    store.upsert_many(
        [
            _job("1", "Senior Backend Engineer", country="GB", days_old=1),
            _job("2", "Backend Engineer", country="GB", days_old=2),
            _job("3", "Frontend Engineer", country="DE", days_old=1),
        ]
    )


def test_frequency_validation(env):
    env.create_alert("u1", {"countries": ["GB"]}, frequency="daily")
    with pytest.raises(env.VantiaError) as exc:
        env.create_alert("u1", {}, frequency="hourly")
    assert exc.value.code == "invalid_frequency"


def test_create_and_list_isolated(env):
    env.create_alert("u1", {"countries": ["GB"]})
    env.create_alert("u2", {"countries": ["DE"]})
    assert len(env.list_alerts("u1")) == 1
    assert len(env.list_alerts("u2")) == 1


def test_filter_matching(env):
    job_gb = {"country": "GB", "title": "Backend Engineer", "visa_sponsorship": True}
    job_de = {"country": "DE", "title": "Backend Engineer", "visa_sponsorship": True}
    assert env.matches_filters(job_gb, {"countries": ["GB"]})
    assert not env.matches_filters(job_de, {"countries": ["GB"]})
    assert env.matches_filters(job_gb, {})  # empty filter matches all
    assert env.matches_filters(job_gb, {"role": "backend"})
    assert not env.matches_filters(job_gb, {"role": "frontend"})
    # sponsorship filter excludes a job that is not flagged sponsored
    job_no_sponsor = {"country": "GB", "title": "Backend Engineer", "visa_sponsorship": False}
    assert env.matches_filters(job_gb, {"sponsorship": True})
    assert not env.matches_filters(job_no_sponsor, {"sponsorship": True})


def test_due_includes_never_sent(env):
    env.create_alert("u1", {"countries": ["GB"]}, frequency="daily")
    assert len(env.due_alerts()) == 1


def test_daily_window_elapsed(env):
    row = env.create_alert("u1", {"countries": ["GB"]}, frequency="daily")
    env.mark_sent(row["id"], now=datetime.now(UTC) - timedelta(hours=25))
    assert len(env.due_alerts()) == 1


def test_daily_window_not_elapsed(env):
    row = env.create_alert("u1", {"countries": ["GB"]}, frequency="daily")
    env.mark_sent(row["id"], now=datetime.now(UTC) - timedelta(hours=2))
    assert len(env.due_alerts()) == 0


def test_jobs_since_excludes_old_and_filters(env):
    alert = env.create_alert("u1", {"countries": ["GB"]}, frequency="daily")
    _seed_jobs()
    jobs = store.search_jobs(verified_only=True)
    fresh = env.jobs_since(alert, jobs)
    # Only GB jobs (DE excluded by the country filter); both are recent.
    assert all(j["country"] == "GB" for j in fresh)
    assert len(fresh) == 2


def test_jobs_since_no_duplicate_after_mark(env):
    alert = env.create_alert("u1", {"countries": ["GB"]}, frequency="daily")
    _seed_jobs()
    jobs = store.search_jobs(verified_only=True)
    first = env.jobs_since(alert, jobs)
    assert first
    # Stamp the window to now → the same jobs are no longer "new".
    env.mark_sent(alert["id"], now=datetime.now(UTC))
    stamped = env.alerts_for("u1")[0]
    assert stamped["last_sent_at"]
    assert env.jobs_since(stamped, jobs) == []


def test_build_digest_top_five(env):
    alert = env.create_alert("u1", {"countries": ["GB"]}, frequency="daily")
    _seed_jobs()
    jobs = store.search_jobs(verified_only=True)
    digest = build_digest(alert, jobs)
    assert digest["count"] == 2
    assert "match your" in digest["subject"]
    assert "•" in digest["body"]
    assert len(digest["jobs"]) <= DIGEST_LIMIT


def test_send_one_dry_run_no_window_advance(env):
    alert = env.create_alert("u1", {"countries": ["GB"]}, frequency="daily")
    _seed_jobs()
    jobs = store.search_jobs(verified_only=True)
    digest = send_one(alert, jobs, dry_run=True)
    assert digest and digest["channel"] == "dry-run"
    # Window NOT advanced on dry-run → still due.
    assert env.due_alerts()


def test_run_summary(env):
    env.create_alert("u1", {"countries": ["GB"]}, frequency="daily")
    _seed_jobs()
    summary = run(dry_run=True)
    assert summary["due"] == 1
    assert summary["sent"] == 1


def test_delete_isolated(env):
    row = env.create_alert("u1", {"countries": ["GB"]})
    with pytest.raises(env.VantiaError) as exc:
        env.delete_alert("u2", row["id"])
    assert exc.value.code == "alert_not_found"
    assert env.delete_alert("u1", row["id"]) is True
    assert env.list_alerts("u1") == []
