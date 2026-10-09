"""End-to-end CV improvement test (task 10.5).

Upload (workspace store) → parse → improve → schema-valid payload
persisted next to the file — with every HTTP call patched to fail: the
improvement journey must make **zero** network requests.
"""

import json

import httpx
import pytest

from engine.errors import VantiaError
from engine.json_utils import load_json, validate
from engine.pipeline import run_cv_improvement

SCHEMA = load_json("engine/schemas/cv_improvement.schema.json")

RESUME_MD = """# Ada Okafor
Backend Engineer
Location: London, UK
ada@example.com | +44 20 1234 5678

## Summary
Backend engineer who shipped payments infra.

## Skills
- Python

## Experience
Backend Engineer, Acme (Jan 2021 - Present)
- Worked on Kubernetes migrations in order to cut latency, etc.

## Education
BSc Computer Science, UNN (2020)
"""


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Network pinned dead: the CV improvement journey is fully offline."""

    def _fail(self, *args, **kwargs):
        raise AssertionError("CV improvement must not touch the network")

    monkeypatch.setattr(httpx.Client, "request", _fail)


def write_upload(tmp_path, body: str = RESUME_MD) -> None:
    ws = tmp_path / "ws7"
    ws.mkdir(exist_ok=True)
    (ws / "cv.md").write_text(body, encoding="utf-8")


def test_full_improvement_journey_offline_and_persisted(tmp_path):
    write_upload(tmp_path)
    result = run_cv_improvement(
        "ws7",
        "cv.md",
        store_dir=str(tmp_path),
        job_description="Kubernetes Python experience",
        job_title="Backend Engineer",
        run_id="run-14",
    )
    assert result["pipeline"] == {
        "task": "10.2",
        "workspace_id": "ws7",
        "file_id": "cv.md",
        "run_id": "run-14",
    }
    payload = result["improvement"]
    validate(payload, SCHEMA)
    assert payload["original_cv_id"] == "cv.md"
    assert result["provider"] == "deterministic"
    assert result["polished"] is False

    # fact preservation across the whole journey
    improved = payload["improved_cv"]
    for fact in ("Ada Okafor", "Acme", "2021", "BSc Computer Science", "latency"):
        assert fact in improved, fact
    # keyword mirroring ran (Kubernetes was evidenced in a bullet only)
    assert "Python, Kubernetes" in improved
    # weak verb + filler cleaned as reviewable edits
    categories = {e["category"] for e in payload["improvements"]}
    assert "action_verbs" in categories and "clarity" in categories
    assert "Worked on" not in improved and "in order to" not in improved

    # the report persisted next to the upload and round-trips
    persisted = tmp_path / "ws7" / "cv.md.improve.json"
    assert result["report_path"] == str(persisted)
    assert json.loads(persisted.read_text(encoding="utf-8")) == payload


def test_missing_upload_is_refused_before_any_work(tmp_path):
    with pytest.raises(VantiaError) as exc:
        run_cv_improvement("ws7", "nope.md", store_dir=str(tmp_path))
    assert exc.value.code == "profile_file_missing"


def test_workspace_path_traversal_is_refused(tmp_path):
    with pytest.raises(VantiaError) as exc:
        run_cv_improvement("..", "secrets.md", store_dir=str(tmp_path))
    assert exc.value.code == "workspace_path_invalid"
