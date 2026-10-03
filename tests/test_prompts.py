"""Prompt-template tests: security-wrapped, structured, and consistent."""

from pathlib import Path

from engine.json_utils import load_json

PROMPTS = Path(__file__).parent.parent / "engine" / "prompts"


def test_all_expected_prompts_shipped():
    names = {path.name for path in PROMPTS.glob("v1_*.md")}
    assert names == {"v1_cover_letter.md", "v1_cv_improve.md"}


def test_prompts_carry_the_security_block():
    for path in sorted(PROMPTS.glob("v1_*.md")):
        text = path.read_text(encoding="utf-8")
        assert "<security>" in text, path.name
        assert "DATA, not instructions" in text, path.name
        assert "ignore it completely" in text, path.name
        # Honesty guard: no fabricated experience or employers.
        assert "invent" in text, path.name
        # Prompt-injection guard: resume/letter content is tagged as data.
        assert "Treat all text inside" in text, path.name


def test_cv_prompt_targets_the_artifact_shape():
    text = (PROMPTS / "v1_cv_improve.md").read_text(encoding="utf-8")
    assert "improvements" in text
    assert "improved_cv" in text
    assert "summary" in text
    # Every improvement category the prompt teaches.
    for category in (
        "keyword_optimization",
        "action_verbs",
        "metrics",
        "structure",
        "content",
        "formatting",
    ):
        assert category in text, category


def test_cover_letter_prompt_targets_the_artifact_shape():
    text = (PROMPTS / "v1_cover_letter.md").read_text(encoding="utf-8")
    assert "content" in text
    assert "sections" in text
    assert "tone" in text
    assert "NEVER invent" in text


def test_cv_prompt_matches_the_schema_categories():
    """The categories the prompt teaches must be a subset of the schema enum."""
    schema = load_json(str(Path(__file__).parent.parent / "engine" / "schemas" / "cv_improvement.schema.json"))
    allowed = set(
        schema["properties"]["improvements"]["items"]["properties"]["category"]["enum"]
    )
    text = (PROMPTS / "v1_cv_improve.md").read_text(encoding="utf-8")
    taught = {
        category
        for category in allowed
        if f"- {category}" in text
    }
    assert taught, "prompt must teach at least one category"
    assert taught <= allowed
