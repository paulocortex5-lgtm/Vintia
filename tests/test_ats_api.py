"""ATS score + status endpoints (task 9.4)."""

import pytest
from fastapi.testclient import TestClient

from engine.json_utils import load_json, validate

SCHEMA = load_json("engine/schemas/ats_score.schema.json")

PROFILE = {
    "name": "Ada Okafor",
    "title": "Backend Engineer",
    "email": "ada@example.com",
    "skills": ["Python", "Kubernetes"],
    "experience": [
        {
            "role": "Backend Engineer",
            "org": "Acme",
            "start": "2021",
            "end": "2024",
            "summary": ["Shipped the payments migration; cut latency by 40%"],
        }
    ],
    "education": ["BSc Computer Science"],
}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    from engine.api import app

    with TestClient(app) as test_client:
        yield test_client


def test_ats_score_returns_schema_valid_report(client):
    response = client.post(
        "/ats/score",
        json={
            "resume": PROFILE,
            "job_title": "Backend Engineer",
            "job_description": "Python Kubernetes. 3 years experience.",
            "job_location": "London",
            "resume_id": "r-9",
            "job_id": "j-9",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema"] == "ats_score.schema.json"
    report = body["report"]
    validate(report, SCHEMA)  # 9.4: schema-valid on every path
    assert report["resume_id"] == "r-9" and report["job_id"] == "j-9"
    assert len(report["category_scores"]) == 12
    assert isinstance(report["missing_keywords"], list)


def test_ats_score_missing_upload_is_422_with_stable_code(client):
    response = client.post("/ats/score", json={"resume": "/nonexistent/resume.pdf"})
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "profile_file_missing"


def test_ats_score_rejects_malformed_bodies(client):
    assert client.post("/ats/score", json={"resume": 123}).status_code == 422
    assert client.post("/ats/score", json={}).status_code == 422


def test_status_reports_the_real_state_shape(client):
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["initialised"] is True
    assert body["total"] == 88
    assert 0 < body["complete"] < body["total"]  # progress is real, ship is not done
    assert body["readiness_pct"] == round(body["complete"] / body["total"] * 100, 1)
    assert body["next_task"] is None or isinstance(body["next_task"], str)
    assert isinstance(body["run_count"], int)


def test_health_still_answers(client):
    assert client.get("/health").json()["status"] == "ok"
