"""Public jobs browse endpoint (live-board backend for ``/jobs``).

``GET /jobs`` renders straight from the ingest store — verified and
active postings only, newest first. Fail-soft by design: an empty
store yields an empty list with ``total: 0``, never a 500.
"""


def _browse_client(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    monkeypatch.setenv("VANTIA_INGEST_DIR", str(tmp_path))
    from fastapi.testclient import TestClient

    from engine.api import app

    return TestClient(app)


def test_jobs_browse_empty_store_is_empty_list(tmp_path, monkeypatch):
    client = _browse_client(tmp_path, monkeypatch)
    response = client.get("/jobs")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["jobs"] == [] and body["total"] == 0


def test_jobs_browse_returns_seeded_jobs_with_clickable_urls(tmp_path, monkeypatch):
    client = _browse_client(tmp_path, monkeypatch)
    assert client.post("/sources/world/seed").status_code == 200
    body = client.get("/jobs").json()
    assert body["total"] > 0
    first = body["jobs"][0]
    assert first["title"] and first["company"] and first["country"]
    assert first["apply_url"].startswith("http")  # every row is clickable
    assert first["link_status"] == "verified"


def test_jobs_browse_filters_by_country_and_role(tmp_path, monkeypatch):
    client = _browse_client(tmp_path, monkeypatch)
    assert client.post("/sources/world/seed").status_code == 200
    ca = client.get("/jobs?country=CA").json()
    assert ca["total"] > 0 and {j["country"] for j in ca["jobs"]} == {"CA"}
    role = client.get("/jobs?role=Microsoft").json()
    assert role["total"] >= 1 and all(
        "microsoft" in j["title"].casefold() or "microsoft" in j["company"].casefold()
        for j in role["jobs"]
    )
    assert len(client.get("/jobs?limit=3").json()["jobs"]) <= 3
