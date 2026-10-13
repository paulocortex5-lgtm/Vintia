"""Link-verification tests (task 15.2 — direct application links).

Every check runs offline: the HEAD function is injected, the store lives in
``tmp_path``. A test job with a 404 URL is marked expired and hidden from
search; a recruiter/aggregator URL is rejected; verified employer and
known-ATS URLs pass.
"""

from datetime import UTC, datetime, timedelta

from engine.sources import ingest_store as store
from engine.sources.verify_links import (
    KNOWN_ATS_DOMAINS,
    apply_domain,
    check_link,
    is_known_ats,
    verify_batch,
)


def _rec(**overrides):
    base = {
        "portal": "greenhouse",
        "external_id": "g1",
        "title": "Backend Engineer",
        "company": "Acme Ltd",
        "url": "https://acme.com/jobs/g1",
        "country": "GB",
        "posted_at": "2026-10-01",
        "description": "A genuine posting.",
        "apply_url": "https://acme.com/apply/g1",
        "apply_url_domain": "acme.com",
        "company_domain": "acme.com",
        "link_status": "unverified",
    }
    base.update(overrides)
    return base


# ── domain helpers ─────────────────────────────────────────────────────


def test_known_ats_domains_ship_with_all_seven():
    assert KNOWN_ATS_DOMAINS == {
        "greenhouse.io",
        "lever.co",
        "myworkdayjobs.com",
        "successfactors.com",
        "icims.com",
        "smartrecruiters.com",
        "workable.com",
    }


def test_is_known_ats_matches_subdomains_but_not_lookalikes():
    assert is_known_ats("boards.greenhouse.io")
    assert is_known_ats("LEVER.CO")
    assert not is_known_ats("recruiter.com")
    assert not is_known_ats("greenhouse.io.evil.com")


def test_apply_domain_parses_and_lowercases():
    assert apply_domain("https://Careers.Acme.COM/apply") == "careers.acme.com"
    assert apply_domain("not a url") == ""
    assert apply_domain("") == ""


# ── check_link rules ───────────────────────────────────────────────────


def test_company_domain_link_verifies():
    check = check_link(_rec(), head_fn=lambda url: 200)
    assert check.status == "verified"
    assert check.reason == "ok"


def test_all_known_ats_links_verify():
    for ats in KNOWN_ATS_DOMAINS:
        rec = _rec(apply_url=f"https://jobs.{ats}/acme/1")
        assert check_link(rec, head_fn=lambda url: 200).status == "verified", ats


def test_http_only_link_is_rejected():
    check = check_link(_rec(apply_url="http://acme.com/apply"), head_fn=lambda url: 200)
    assert check.status == "rejected"
    assert check.reason == "not_https"


def test_middleman_link_is_rejected():
    check = check_link(_rec(apply_url="https://recruiter.com/apply/1"), head_fn=lambda url: 200)
    assert check.status == "rejected"
    assert "middleman_or_mismatch" in check.reason


def test_missing_apply_url_is_rejected():
    check = check_link(_rec(apply_url=""), head_fn=lambda url: 200)
    assert check.status == "rejected"
    assert check.reason == "no_apply_url"


def test_404_link_is_expired():
    check = check_link(_rec(), head_fn=lambda url: 404)
    assert check.status == "expired"
    assert check.reason == "dead_status:404"


def test_gone_and_unavailable_links_are_expired():
    assert check_link(_rec(), head_fn=lambda url: 410).status == "expired"
    assert check_link(_rec(), head_fn=lambda url: 451).status == "expired"


def test_transient_failure_is_stale_not_expired():
    check = check_link(_rec(), head_fn=lambda url: 503)
    assert check.status == "stale"


def test_fee_language_link_is_rejected():
    rec = _rec(description="Pay a processing fee of USD 200 to apply.")
    check = check_link(rec, head_fn=lambda url: 200)
    assert check.status == "rejected"
    assert check.reason == "fee_language"


# ── verify_batch ───────────────────────────────────────────────────────


def test_verify_batch_marks_verified_and_expired(tmp_path):
    store_dir = str(tmp_path)
    good = store.JobRecord(
        portal="lever",
        external_id="l1",
        title="Designer",
        company="Beta",
        url="https://beta.com/j/l1",
        apply_url="https://beta.com/apply/l1",
        apply_url_domain="beta.com",
        company_domain="beta.com",
        description="Real role.",
    )
    dead = store.JobRecord(
        portal="lever",
        external_id="l2",
        title="Designer",
        company="Beta",
        url="https://beta.com/j/l2",
        apply_url="https://beta.com/apply/l2",
        company_domain="beta.com",
        description="Real role.",
    )
    store.upsert_many([good, dead], store_dir=store_dir)

    def head(url):
        return 200 if url.endswith("/l1") else 404

    counts = verify_batch(50, store_dir=store_dir, head_fn=head)
    assert counts == {"checked": 2, "verified": 1, "expired": 1, "rejected": 0, "stale": 0}

    jobs = store.load_jobs(store_dir)
    assert jobs["lever:l1"]["link_status"] == "verified"
    assert jobs["lever:l1"]["link_expires_at"] is not None
    assert jobs["lever:l2"]["link_status"] == "expired"
    assert jobs["lever:l2"]["link_expires_at"] is None

    # Expired jobs are hidden from search (user-facing guarantee §6.6).
    visible = store.search_jobs(store_dir=store_dir)
    assert [j["external_id"] for j in visible] == ["l1"]


def test_verify_batch_prioritises_unverified_then_stale(tmp_path):
    store_dir = str(tmp_path)
    old = (datetime.now(UTC) - timedelta(hours=30)).isoformat()
    fresh = datetime.now(UTC).isoformat()
    stale = store.JobRecord(
        portal="wd",
        external_id="s",
        title="Ops",
        company="Gamma",
        url="https://gamma.com/s",
        apply_url="https://gamma.com/a",
        company_domain="gamma.com",
        description="Real.",
        link_status="verified",
        link_checked_at=old,
        link_expires_at=old,
    )
    recent = store.JobRecord(
        portal="wd",
        external_id="r",
        title="Ops",
        company="Gamma",
        url="https://gamma.com/r",
        apply_url="https://gamma.com/a",
        company_domain="gamma.com",
        description="Real.",
        link_status="verified",
        link_checked_at=fresh,
        link_expires_at=fresh,
    )
    fresh_unverified = store.JobRecord(
        portal="wd",
        external_id="n",
        title="Ops",
        company="Gamma",
        url="https://gamma.com/n",
        apply_url="https://gamma.com/a",
        company_domain="gamma.com",
        description="Real.",
    )
    store.upsert_many([stale, recent, fresh_unverified], store_dir=store_dir)

    counts = verify_batch(50, store_dir=store_dir, head_fn=lambda url: 200)
    # unverified (n) + stale older than 6h (s); the fresh one is left alone.
    assert counts["checked"] == 2
    jobs = store.load_jobs(store_dir)
    assert jobs["wd:r"]["link_checked_at"] == fresh
