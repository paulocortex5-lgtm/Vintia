"""Keyword matcher + gap analysis tests (task 9.3)."""

import pytest

from engine.ats.keywords import (
    gap_report,
    job_keywords,
    keyword_coverage,
    match_keywords,
    normalise,
    resume_keywords,
    stem,
)
from engine.ats.parser import parse_resume


def test_normalise_casefolds_strips_accents_and_punctuation():
    out = normalise("Café SQL, please!")
    assert "cafe" in out and "sql" in out
    assert "!" not in out and "é" not in out


def test_stemmer_converges_known_variants_and_keeps_short_tokens():
    assert stem("databases") == stem("database") == "database"
    assert stem("optimizes") == stem("optimize") == "optimize"
    assert stem("cities") == stem("city") == "city"
    assert stem("shipping") == stem("ship") == "ship"
    assert stem("go") == "go"  # short tokens untouched
    # technical words survive through the alias layer, not the stemmer:
    matched, missing, _how = match_keywords(["kubernetes", "PostgreSQL"], ["k8s", "psql"])
    assert set(matched) == {"kubernetes", "PostgreSQL"}
    assert missing == []


def test_job_keywords_filters_stopwords_keeps_phrases_and_merges_title():
    keywords = job_keywords(
        "We want Python and Kubernetes for our team; the usual, great work.",
        title="Backend Engineer",
    )
    assert "python" in keywords and "kubernetes" in keywords
    assert "the" not in keywords and "team" not in keywords and "great" not in keywords
    assert "backend" in keywords and "engineer" in keywords  # title tokens merged
    assert keywords == sorted(set(keywords))  # stable, de-duplicated output


def test_job_keywords_detects_multi_word_phrases():
    keywords = job_keywords("experience with machine learning pipelines and node.js services")
    assert "machine learning" in keywords
    assert "node.js" in keywords


def test_job_keywords_rejects_nonsense_min_len():
    with pytest.raises(ValueError):
        job_keywords("whatever", min_len=0)


def test_resume_keywords_span_skills_experience_and_education():
    resume = parse_resume(
        {
            "skills": ["PostgreSQL"],
            "experience": [{"role": "Data Scientist", "org": "Acme", "summary": ["built models"]}],
            "education": ["MSc Data Science"],
        }
    )
    keywords = resume_keywords(resume)
    assert "postgresql" in keywords
    assert "scientist" in keywords
    assert "models" in keywords


def test_match_keywords_exact_stem_synonym_and_missing():
    matched, missing, how = match_keywords(
        ["PostgreSQL", "k8s", "databases", "cobol"],
        ["postgres", "kubernetes", "database"],
    )
    assert set(matched) == {"PostgreSQL", "k8s", "databases"}
    assert missing == ["cobol"]
    assert how["PostgreSQL"] in {"synonym", "stem"}
    assert how["k8s"] in {"synonym", "stem"}
    assert set(how) == set(matched)


def test_match_keywords_case_insensitive_exact():
    matched, missing, how = match_keywords(["PYTHON"], ["python"])
    assert matched == ["PYTHON"] and missing == [] and how["PYTHON"] == "exact"


def test_coverage_zero_required_is_one_and_fraction_rounds():
    assert keyword_coverage([], []) == 1.0
    assert keyword_coverage(["a", "b"], ["a"]) == 0.5
    assert keyword_coverage(["a", "b"], ["a", "b"]) == 1.0


def test_gap_report_is_placement_honest():
    suggestions = gap_report(["cobol", "python"], ["python"], ["cobol"], {})
    assert len(suggestions) == 1
    only = suggestions[0]
    assert only["category"] == "keyword_match"
    assert only["priority"] in {"high", "medium"}
    assert "genuinely hold" in only["suggestion"]  # never coaches fabrication


def test_gap_report_low_priority_note_for_covered_keywords():
    suggestions = gap_report(["PostgreSQL"], ["PostgreSQL"], [], {"PostgreSQL": "synonym"})
    assert suggestions and suggestions[0]["priority"] == "low"
    assert "synonym" in suggestions[0]["suggestion"]
