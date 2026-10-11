"""Interactive product endpoints backing the workspace UI (tasks 13.2–13.4).

``POST /ats/upload`` (multipart file → schema-valid report),
``POST /improve/cv`` and ``POST /cover/letter`` — deterministic, unmetered
and honest on every failure path: empty upload, oversize upload,
unparseable resume, cover letter against an empty posting.
"""

import pytest
from fastapi.testclient import TestClient

from engine.json_utils import load_json, validate

ATS_SCHEMA = load_json("engine/schemas/ats_score.schema.json")
IMPROVE_SCHEMA = load_json("engine/schemas/cv_improvement.schema.json")
COVER_SCHEMA = load_json("engine/schemas/cover_letter.schema.json")

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

RESUME_MD = """# Ada Okafor
Backend Engineer
Location: London, UK
ada@example.com | +44 20 1234 5678

## Summary
Backend engineer who shipped payments infra and cut latency by 40%.

## Skills
- Python, Kubernetes, PostgreSQL

## Experience
Backend Engineer, Acme (Jan 2021 - Present)
- Shipped the migration; cut p95 latency by 40%

## Education
BSc Computer Science, UNN (2020)
"""

JD = "Python Kubernetes PostgreSQL. 3 years experience."


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("VANTIA_SELF_PING", "0")
    from engine.api import app

    with TestClient(app) as test_client:
        yield test_client


# ── 13.2: /ats/upload ─────────────────────────────────────────────────


def test_ats_upload_scores_a_text_file_upload(client):
    response = client.post(
        "/ats/upload",
        files={"file": ("resume.md", RESUME_MD.encode("utf-8"), "text/markdown")},
        data={"job_title": "Backend Engineer", "job_description": JD, "job_location": "London"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema"] == "ats_score.schema.json"
    validate(body["report"], ATS_SCHEMA)  # schema-valid on the upload path too
    assert body["report"]["resume_id"] == "resume.md"
    assert len(body["report"]["category_scores"]) == 12
    assert isinstance(body["parser"]["warnings"], list)


def test_ats_upload_matches_the_paste_path_score(client):
    """The same resume + JD must score identically whether uploaded or pasted."""
    uploaded = client.post(
        "/ats/upload",
        files={"file": ("resume.md", RESUME_MD.encode("utf-8"), "text/markdown")},
        data={"job_description": JD},
    ).json()["report"]
    pasted = client.post(
        "/ats/score", json={"resume_text": RESUME_MD, "job_description": JD}
    ).json()["report"]
    assert uploaded["overall_score"] == pasted["overall_score"]
    assert uploaded["category_scores"] == pasted["category_scores"]


def test_ats_score_without_any_resume_is_422_resume_required(client):
    response = client.post("/ats/score", json={"job_description": JD})
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "resume_required"


def test_ats_upload_empty_file_is_422_upload_empty(client):
    response = client.post(
        "/ats/upload",
        files={"file": ("resume.md", b"", "text/markdown")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "upload_empty"


def test_ats_upload_oversize_is_413_with_stable_code(client, monkeypatch):
    monkeypatch.setenv("VANTIA_MAX_FILE_SIZE_MB", "1")
    big = b"x" * (1024 * 1024 + 1)
    response = client.post(
        "/ats/upload",
        files={"file": ("resume.md", big, "text/markdown")},
    )
    assert response.status_code == 413
    detail = response.json()["detail"]
    assert detail["error"] == "upload_too_large"
    assert detail["context"]["limit_bytes"] == 1024 * 1024


def test_ats_upload_unparseable_binary_is_422_not_an_empty_score(client):
    response = client.post(
        "/ats/upload",
        files={"file": ("resume.bin", b"\xff\xfe\x00\x00garbage", "application/octet-stream")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "profile_format_unsupported"


# ── 13.3: /improve/cv ─────────────────────────────────────────────────


def test_improve_cv_returns_schema_valid_deterministic_improvement(client):
    response = client.post(
        "/improve/cv",
        json={"resume": PROFILE, "job_description": JD, "resume_id": "cv-13"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema"] == "cv_improvement.schema.json"
    assert body["provider"] == "deterministic" and body["polished"] is False
    validate(body["improvement"], IMPROVE_SCHEMA)
    assert body["improvement"]["original_cv_id"] == "cv-13"  # identity re-stamped


def test_improve_cv_unparseable_resume_is_422(client):
    response = client.post("/improve/cv", json={"resume": "/nonexistent/cv.pdf"})
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "profile_file_missing"


def test_improve_cv_requires_the_resume_field(client):
    assert client.post("/improve/cv", json={}).status_code == 422


# ── 13.4: /cover/letter ───────────────────────────────────────────────


def test_cover_letter_uses_only_the_pasted_facts(client):
    response = client.post(
        "/cover/letter",
        json={
            "resume": PROFILE,
            "job_title": "Backend Engineer",
            "company": "Acme Robotics Ltd",
            "job_description": JD,
            "job_location": "London",
            "resume_id": "cv-14",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema"] == "cover_letter.schema.json"
    assert body["provider"] == "deterministic"
    validate(body["cover_letter"], COVER_SCHEMA)
    payload = body["cover_letter"]
    assert payload["job_id"].startswith("manual-")  # caller-pasted posting, stamped as such
    assert payload["metadata"]["company_name"] == "Acme Robotics Ltd"


def test_cover_letter_against_an_empty_posting_is_422_job_required(client):
    response = client.post("/cover/letter", json={"resume": PROFILE})
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "job_required"


def test_cover_letter_unparseable_resume_is_422(client):
    response = client.post(
        "/cover/letter", json={"resume": "/nonexistent/cv.pdf", "job_title": "Dev"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "profile_file_missing"
