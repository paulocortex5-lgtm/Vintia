"""End-to-end scholarship pipeline test (task 3.7).

The full journey — database lookup → profile load → credential mapping
→ window status → SOP + research proposal — entirely offline: the
pipeline performs no I/O beyond reading the caller's background file,
and the test pins that guarantee by making any httpx call fail the run.
Both artifact payloads are validated against the schemas shipped in
tasks 1.2/1.3.
"""

import json
from datetime import date

import httpx
import pytest

from engine.errors import VantiaError
from engine.json_utils import load_json, validate
from engine.pipeline import run_scholarship_pipeline

SOP_SCHEMA = load_json("engine/schemas/sop.schema.json")
PROPOSAL_SCHEMA = load_json("engine/schemas/research_proposal.schema.json")

PROFILE = {
    "name": "Ada Okafor",
    "title": "Backend Engineer",
    "summary": "I build reliable systems and want to move into applied ML research.",
    "skills": ["Python", "Kubernetes", "Torch", "PostgreSQL"],
    "experience": [
        {
            "role": "SRE",
            "org": "Acme",
            "start": "2022",
            "end": "2026",
            "summary": ["Kept lights on"],
        }
    ],
    "education": [{"degree": "BSc Computer Science", "school": "UNN", "year": "2020"}],
    "languages": ["English"],
}

CAREER_GOAL = "Lead an applied-ML team returning to my home country within five years."


def write_profile(tmp_path, data: dict) -> str:
    path = tmp_path / "background.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_full_journey_produces_schema_valid_artifacts(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):  # pragma: no cover — must never run
        raise AssertionError("scholarship pipeline must not touch the network")

    monkeypatch.setattr(httpx.Client, "request", no_network)

    result = run_scholarship_pipeline(
        "erasmus-mundus",
        "machine learning",
        write_profile(tmp_path, PROFILE),
        CAREER_GOAL,
        research_interests="efficient machine learning on limited data",
        applicant_id="app-1",
        today=date(2026, 10, 6),
        run_id="e2e",
    )

    assert sorted(result) == ["credential", "pipeline", "proposal", "scholarship", "sop", "window"]
    assert result["pipeline"] == {
        "task": "3.6",
        "scholarship_id": "erasmus-mundus",
        "field": "machine learning",
        "run_id": "e2e",
    }
    assert result["scholarship"]["url"].startswith("https://erasmus-plus.ec.europa.eu/")

    # window: informational, read against the injected day
    assert result["window"]["status"] == "open"
    assert result["window"]["days_left"] == 117  # 2026-10-06 → 2027-01-31

    # credential: BSc → EQF 6 → meets the master's entry level
    assert result["credential"]["meets_level"] is True
    assert result["credential"]["credential"]["eqf_level"] == 6

    # both artifacts validate against the shipped schemas
    validate(result["sop"]["payload"], SOP_SCHEMA)
    validate(result["proposal"]["payload"], PROPOSAL_SCHEMA)
    assert result["sop"]["provider"] == "deterministic"
    assert result["proposal"]["provider"] == "deterministic"
    assert "Acme" in result["sop"]["content"]
    assert CAREER_GOAL in result["sop"]["content"]


def test_window_never_gates_the_run(tmp_path):
    # 2027-05-01: Chevening's cycle is months away — preparation still happens
    result = run_scholarship_pipeline(
        "chevening",
        "public policy",
        write_profile(tmp_path, PROFILE),
        CAREER_GOAL,
        today=date(2027, 5, 1),
    )
    assert result["window"]["status"] == "upcoming"
    assert result["window"]["opens"] == "2027-08-01"
    assert result["sop"]["payload"]["scholarship_id"] == "chevening"
    validate(result["proposal"]["payload"], PROPOSAL_SCHEMA)


def test_sub_bachelor_credential_reports_false_but_still_runs(tmp_path):
    data = {**PROFILE, "education": [{"degree": "HND", "school": "Poly", "year": "2019"}]}
    result = run_scholarship_pipeline(
        "erasmus-mundus", "engineering", write_profile(tmp_path, data), CAREER_GOAL
    )
    assert result["credential"]["meets_level"] is False  # informational, never a gate
    assert result["credential"]["credential"]["id"] == "gb-hnd"
    validate(result["sop"]["payload"], SOP_SCHEMA)


def test_profile_without_education_yields_an_honest_none(tmp_path):
    data = {k: v for k, v in PROFILE.items() if k != "education"}
    result = run_scholarship_pipeline(
        "daad", "data science", write_profile(tmp_path, data), CAREER_GOAL
    )
    assert result["credential"]["meets_level"] is None
    assert "no education entry" in result["credential"]["advice"]
    assert result["window"]["status"] == "unknown"  # DAAD has no embedded window
    validate(result["sop"]["payload"], SOP_SCHEMA)


def test_markdown_background_feeds_the_same_journey(tmp_path):
    path = tmp_path / "cv.md"
    path.write_text(
        "# Ada Okafor\n## Backend Engineer\n\nBuilds systems.\n\n"
        "## Skills\n- Python\n- Torch\n- Kubernetes\n\n"
        "## Education\n- BSc Computer Science, UNN (2020)\n",
        encoding="utf-8",
    )
    result = run_scholarship_pipeline(
        "chevening", "machine learning", str(path), CAREER_GOAL, today=date(2026, 10, 6)
    )
    # the markdown parser keeps education prose outside structured entries —
    # the credential check stays honest about that
    assert result["credential"]["meets_level"] is None
    validate(result["sop"]["payload"], SOP_SCHEMA)
    validate(result["proposal"]["payload"], PROPOSAL_SCHEMA)


def test_unknown_scholarship_fails_before_touching_the_profile(tmp_path):
    with pytest.raises(VantiaError) as excinfo:
        run_scholarship_pipeline("nope", "ml", str(tmp_path / "absent.json"), CAREER_GOAL)
    assert excinfo.value.code == "scholarship_not_found"


def test_sparse_inputs_refuse_fake_keywords(tmp_path):
    data = {"name": "X", "title": ""}
    with pytest.raises(VantiaError) as excinfo:
        run_scholarship_pipeline(
            "daad", "", write_profile(tmp_path, data), "", research_interests=""
        )
    assert excinfo.value.code == "proposal_keywords_insufficient"
