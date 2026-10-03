"""Schema tests: every shipped JSON Schema parses and round-trips samples."""

from pathlib import Path

from engine.errors import SchemaValidationError
from engine.json_utils import load_json, validate

SCHEMAS = Path(__file__).parent.parent / "engine" / "schemas"


def test_every_schema_parses():
    schemas = sorted(SCHEMAS.glob("*.schema.json"))
    assert len(schemas) >= 4
    for path in schemas:
        schema = load_json(str(path))
        assert schema["$schema"].startswith("https://json-schema.org/draft/2020-12")
        assert schema["type"] == "object"


def test_envelope_accepts_a_minimal_artifact():
    schema = load_json(str(SCHEMAS / "envelope.schema.json"))
    instance = {
        "schema_version": 1,
        "task_id": "2.7",
        "created_at": "2026-10-03T22:00:00Z",
        "payload": {"name": "Ada"},
    }
    assert validate(instance, schema) == []


def test_envelope_rejects_unknown_keys():
    schema = load_json(str(SCHEMAS / "envelope.schema.json"))
    instance = {
        "schema_version": 1,
        "task_id": "2.7",
        "created_at": "2026-10-03T22:00:00Z",
        "payload": {},
        "not_a_field": True,
    }
    try:
        validate(instance, schema)
        assert False, "expected SchemaValidationError"
    except SchemaValidationError as exc:
        assert exc.code == "schema_violation"


def test_cv_improvement_schema_roundtrip():
    schema = load_json(str(SCHEMAS / "cv_improvement.schema.json"))
    instance = {
        "original_cv_id": "cv_1",
        "improvements": [
            {
                "category": "action_verbs",
                "section": "Professional Experience",
                "original_text": "worked on a dashboard",
                "improved_text": "engineered a dashboard",
                "reason": "stronger verb",
                "impact": "high",
                "priority": 9,
            }
        ],
        "improved_cv": "Ada Lovelace\nEngineered dashboards.",
        "summary": {
            "total_improvements": 1,
            "high_impact_count": 1,
            "medium_impact_count": 0,
            "low_impact_count": 0,
        },
    }
    assert validate(instance, schema) == []
    instance["improvements"][0]["impact"] = "huge"
    try:
        validate(instance, schema)
        assert False, "expected SchemaValidationError for bad impact enum"
    except SchemaValidationError as exc:
        assert exc.errors


def test_ats_score_schema_all_twelve_categories():
    schema = load_json(str(SCHEMAS / "ats_score.schema.json"))
    categories = {
        "formatting",
        "contact_info",
        "keyword_match",
        "job_title_match",
        "years_experience",
        "skills_match",
        "education_match",
        "certifications_match",
        "language_match",
        "location_match",
        "employment_gaps",
        "overall_impact",
    }
    assert set(schema["properties"]["category_scores"]["properties"]) == categories
    instance = {
        "resume_id": "r1",
        "job_id": "j1",
        "overall_score": 72.5,
        "category_scores": {name: 72.5 for name in categories},
        "keyword_coverage": 0.65,
        "matched_keywords": ["python"],
        "missing_keywords": ["django"],
        "improvement_suggestions": [
            {"category": "keyword_match", "suggestion": "add django", "priority": "high"}
        ],
    }
    assert validate(instance, schema) == []


def test_cover_letter_schema_roundtrip():
    schema = load_json(str(SCHEMAS / "cover_letter.schema.json"))
    instance = {
        "resume_id": "r1",
        "job_id": "j1",
        "content": "x" * 120,
        "sections": [{"heading": "Opening", "body": "hello", "word_count": 1}],
        "metadata": {
            "company_name": "Vantia",
            "job_title": "Engineer",
            "total_word_count": 300,
            "generated_at": "2026-10-03T22:00:00Z",
            "tone": "professional",
        },
    }
    assert validate(instance, schema) == []
    instance["content"] = "too short"
    try:
        validate(instance, schema)
        assert False, "expected SchemaValidationError for short content"
    except SchemaValidationError as exc:
        assert exc.code == "schema_violation"
