"""Profile loader tests (task 2.8 support) — JSON and markdown resumes."""

import json

import pytest

from engine.errors import VantiaError
from engine.generators import load_profile

JSON_PROFILE = {
    "name": "Ada Okafor",
    "title": "Backend Engineer",
    "email": "ada@example.com",
    "summary": "Ships reliable services.",
    "skills": ["Python", "Kubernetes", "PostgreSQL"],
    "experience": [
        {"role": "SRE", "org": "Acme", "start": "2022", "end": "2026", "summary": "Kept lights on"}
    ],
    "education": [{"degree": "BSc Computer Science", "school": "UNN", "year": "2020"}],
    "languages": ["English", "Igbo"],
    "unknown_field": "ignored",
}

MD_RESUME = """# Ada Okafor
## Backend Engineer

Summary of my work so far.

## Skills
- Python
- Kubernetes
- Terraform

## Experience
Built things at Acme.
"""


def test_json_profile_parses_every_known_field(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(JSON_PROFILE), encoding="utf-8")
    profile = load_profile(str(path))
    assert profile.name == "Ada Okafor"
    assert profile.title == "Backend Engineer"
    assert profile.skills == ("Python", "Kubernetes", "PostgreSQL")
    assert profile.languages == ("English", "Igbo")
    assert profile.experience[0].role == "SRE"
    assert profile.experience[0].summary == ("Kept lights on",)
    assert profile.education[0].degree.startswith("BSc")
    assert not hasattr(profile, "unknown_field")


def test_json_profile_accepts_comma_skills_and_string_entries(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(
        json.dumps({"name": "X", "title": "Y", "skills": "Go, Rust", "experience": ["Clerk"]}),
        encoding="utf-8",
    )
    profile = load_profile(str(path))
    assert profile.skills == ("Go", "Rust")
    assert profile.experience[0].role == "Clerk"


def test_json_profile_with_skills_as_objects(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"name": "X", "skills": [{"name": "Go"}, "Rust"]}), encoding="utf-8")
    assert load_profile(str(path)).skills == ("Go", "Rust")


def test_markdown_profile_splits_name_title_skills_and_summary(tmp_path):
    path = tmp_path / "resume.md"
    path.write_text(MD_RESUME, encoding="utf-8")
    profile = load_profile(str(path))
    assert profile.name == "Ada Okafor"
    assert profile.title == "Backend Engineer"
    assert profile.skills == ("Python", "Kubernetes", "Terraform")
    assert "Built things at Acme" in profile.summary
    assert "Kubernetes" not in profile.summary  # skills live outside the summary


def test_plain_text_profile_without_headings_or_skills(tmp_path):
    path = tmp_path / "resume.txt"
    path.write_text("First line is the name.\nJust prose after that.\n", encoding="utf-8")
    profile = load_profile(str(path))
    assert profile.name == "First line is the name."
    assert profile.title == ""
    assert profile.skills == ()


def test_missing_file_unsupported_format_and_bad_json(tmp_path):
    with pytest.raises(VantiaError) as excinfo:
        load_profile(str(tmp_path / "absent.json"))
    assert excinfo.value.code == "profile_file_missing"

    cv = tmp_path / "cv.pdf"
    cv.write_text("binary-ish", encoding="utf-8")
    with pytest.raises(VantiaError) as excinfo:
        load_profile(str(cv))
    assert excinfo.value.code == "profile_format_unsupported"

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(VantiaError) as excinfo:
        load_profile(str(broken))
    assert excinfo.value.code == "profile_parse_error"

    not_object = tmp_path / "list.json"
    not_object.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(VantiaError) as excinfo:
        load_profile(str(not_object))
    assert excinfo.value.code == "profile_parse_error"
