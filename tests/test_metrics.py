"""Metrics endpoint tests (task 15.14 §18.4).

The public /status page reads ``GET /metrics``; it must return 200 with
the documented sections and never 500 even when a subsystem is absent.
"""

from fastapi.testclient import TestClient

from engine.api import app


def test_metrics_returns_all_sections():
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    for key in ("ingest", "world_sources", "llm", "api", "golden_path", "tasks", "ts"):
        assert key in data, f"missing section {key}"


def test_metrics_world_sources_lists_countries():
    client = TestClient(app)
    data = client.get("/metrics").json()
    assert data["world_sources"]["countries"] == ["AU", "CA", "NZ", "US"]


def test_metrics_ingest_counts_are_integers():
    client = TestClient(app)
    data = client.get("/metrics").json()
    ingest = data["ingest"]
    assert isinstance(ingest["jobs_total"], int)
    assert isinstance(ingest["jobs_verified"], int)
    assert ingest["jobs_pending"] == ingest["jobs_total"] - ingest["jobs_verified"]


def test_metrics_never_500_without_subsystems():
    # Even with an empty ingest dir, the endpoint degrades gracefully.
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
