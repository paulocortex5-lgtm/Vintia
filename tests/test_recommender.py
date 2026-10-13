"""Recommendation tests (task 15.1 — job recommendations from CV).

Offline: seeded ingest store in ``tmp_path``, pasted-text CVs through the
real parser. Covers ranking order, weights, caching, the unparseable-CV
fallback and the ≤20 limit.
"""

from datetime import UTC, datetime, timedelta

from engine.ats.parser import parse_resume
from engine.ats.recommender import MATCH_WEIGHTS, RECOMMENDATION_LIMIT, recommend
from engine.sources import ingest_store as store

CV = """Jane Doe
Senior Backend Engineer

Skills
Python, Django, PostgreSQL, Kubernetes, AWS, Redis

Experience
Senior Backend Engineer at Acme (Jan 2020 - Jan 2026): built Django
services on PostgreSQL, deployed on Kubernetes and AWS.
Backend Engineer at Beta (Jan 2017 - Dec 2019): Django REST APIs.

Education
- MSc Computer Science, University of London, 2016
"""


def _job(
    external_id,
    title,
    description,
    *,
    country="GB",
    posted_at="2026-10-10",
    sponsorship=True,
    company="Acme",
):
    return store.JobRecord(
        portal="greenhouse",
        external_id=external_id,
        title=title,
        company=company,
        url=f"https://{company.lower()}.com/jobs/{external_id}",
        country=country,
        posted_at=posted_at,
        description=description,
        visa_sponsorship=sponsorship,
        apply_url=f"https://{company.lower()}.com/apply/{external_id}",
        company_domain=f"{company.lower()}.com",
        link_status="verified",
    )


def _seed(store_dir: str, now: datetime) -> None:
    jobs = [
        _job(
            "1",
            "Senior Python Engineer",
            "5+ years Python, Django, PostgreSQL, Kubernetes, AWS. Bachelor degree required.",
            posted_at=(now - timedelta(days=2)).strftime("%Y-%m-%d"),
        ),
        _job(
            "2",
            "Frontend React Developer",
            "React, TypeScript, CSS. 3 years experience.",
            posted_at=(now - timedelta(days=3)).strftime("%Y-%m-%d"),
            sponsorship=False,
        ),
        _job(
            "3",
            "Data Engineer",
            "Python, Spark, SQL, 5 years. Master degree required.",
            country="DE",
            posted_at=(now - timedelta(days=30)).strftime("%Y-%m-%d"),
            company="Gamma",
        ),
        _job(
            "4",
            "Python Developer (Junior)",
            "Python, Django. No degree requirement.",
            posted_at=(now - timedelta(days=1)).strftime("%Y-%m-%d"),
            company="Delta",
        ),
    ]
    store.upsert_many(jobs, store_dir=store_dir)


def test_weights_sum_to_one():
    assert abs(sum(MATCH_WEIGHTS.values()) - 1.0) < 1e-9


def _with_store(tmp_path, monkeypatch, now=None):
    store_dir = str(tmp_path / "ingest")
    monkeypatch.setenv("VANTIA_INGEST_DIR", store_dir)
    _seed(store_dir, now or datetime.now(UTC))
    return store_dir


def test_matching_backend_role_ranks_first(tmp_path, monkeypatch):
    _with_store(tmp_path, monkeypatch)
    resume = parse_resume(CV.encode("utf-8"), content_type="text/plain")
    result = recommend(resume, filters={"countries": ["GB"]})
    jobs = result["jobs"]
    assert 0 < len(jobs) <= RECOMMENDATION_LIMIT
    assert jobs[0]["job_id"] == "greenhouse:1"
    scores = [j["match_score"] for j in jobs]
    assert scores == sorted(scores, reverse=True)
    assert jobs[0]["match_score"] > jobs[-1]["match_score"]


def test_matched_skills_are_reported(tmp_path, monkeypatch):
    _with_store(tmp_path, monkeypatch)
    resume = parse_resume(CV.encode("utf-8"), content_type="text/plain")
    result = recommend(resume, filters={"countries": ["GB"]})
    top = next(j for j in result["jobs"] if j["job_id"] == "greenhouse:1")
    assert top["matched_skills"], "top match must report shared skills"
    assert len(top["matched_skills"]) <= 3


def test_country_filter_is_applied(tmp_path, monkeypatch):
    _with_store(tmp_path, monkeypatch)
    resume = parse_resume(CV.encode("utf-8"), content_type="text/plain")
    de = recommend(resume, filters={"countries": ["DE"]})
    assert all(j["country"] == "DE" for j in de["jobs"])


def test_role_filter_is_applied(tmp_path, monkeypatch):
    _with_store(tmp_path, monkeypatch)
    resume = parse_resume(CV.encode("utf-8"), content_type="text/plain")
    result = recommend(resume, filters={"role": "Frontend"})
    assert result["jobs"]
    assert all("frontend" in j["title"].lower() for j in result["jobs"])


def test_cached_result_returns_instantly(tmp_path, monkeypatch):
    _with_store(tmp_path, monkeypatch)
    resume = parse_resume(CV.encode("utf-8"), content_type="text/plain")
    first = recommend(resume, filters={"countries": ["GB"]})
    assert first["cached"] is False
    second = recommend(resume, filters={"countries": ["GB"]})
    assert second["cached"] is True
    assert second["jobs"] == first["jobs"]


def test_expired_cache_is_recomputed(tmp_path, monkeypatch):
    store_dir = _with_store(tmp_path, monkeypatch)
    resume = parse_resume(CV.encode("utf-8"), content_type="text/plain")
    recommend(resume, filters={"countries": ["GB"]})
    # Age the cache entry past the 24h TTL.
    import json

    from engine.json_utils import atomic_write_json

    path = store_dir + "/recommendations.json"
    with open(path, encoding="utf-8") as fh:
        data = json.loads(fh.read())
    old = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    for entry in data["entries"].values():
        entry["created_at"] = old
    atomic_write_json(path, data)
    again = recommend(resume, filters={"countries": ["GB"]})
    assert again["cached"] is False


def test_unparseable_cv_falls_back_with_note(tmp_path, monkeypatch):
    _with_store(tmp_path, monkeypatch)
    result = recommend(None, filters={"countries": ["GB"]})
    assert result["note"], "fallback must explain why the list is generic"
    assert "could not be parsed" in result["note"]
    assert 0 < len(result["jobs"]) <= RECOMMENDATION_LIMIT
    assert all(j["match_score"] == 0.0 for j in result["jobs"])


def test_empty_cv_text_is_the_fallback(tmp_path, monkeypatch):
    _with_store(tmp_path, monkeypatch)
    # the parser refuses empty text outright — recommend() must treat that
    # exactly like an unparseable CV (documented fallback, no error page).
    import pytest

    from engine.errors import VantiaError

    with pytest.raises(VantiaError):
        parse_resume(b"", content_type="text/plain")
    result = recommend(None)
    assert result["note"]


def test_visas_and_recency_influence_ranking(tmp_path, monkeypatch):
    _with_store(tmp_path, monkeypatch)
    resume = parse_resume(CV.encode("utf-8"), content_type="text/plain")
    result = recommend(resume, filters={"countries": ["GB"]})
    by_id = {j["job_id"]: j for j in result["jobs"]}
    # sponsored + fresh junior Python role outranks the unsponsored frontend role
    assert by_id["greenhouse:4"]["match_score"] > by_id["greenhouse:2"]["match_score"]


def test_recommendations_never_include_unverified_jobs(tmp_path, monkeypatch):
    store_dir = _with_store(tmp_path, monkeypatch)
    bad = _job("9", "Scam Python Role", "Python", company="Shady")
    bad.link_status = "rejected"
    store.upsert(bad, store_dir=store_dir)
    resume = parse_resume(CV.encode("utf-8"), content_type="text/plain")
    result = recommend(resume, filters={})
    assert all(j["link_status"] == "verified" for j in result["jobs"])
    assert "greenhouse:9" not in {j["job_id"] for j in result["jobs"]}
