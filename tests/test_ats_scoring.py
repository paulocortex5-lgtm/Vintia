"""ATS scoring engine tests (task 9.2) — the twelve-point rubric."""

import pytest

from engine.ats import score_resume
from engine.ats.parser import parse_resume
from engine.ats.scoring import CATEGORY_WEIGHTS, ScoreReport
from engine.json_utils import load_json, validate

SCHEMA = load_json("engine/schemas/ats_score.schema.json")


def rich_resume():
    """A complete, honest profile: dated spans, contact, skills, education."""
    return parse_resume(
        {
            "name": "Ada Okafor",
            "title": "Backend Engineer",
            "email": "ada@example.com",
            "phone": "+234 801 234 5678",
            "location": "Lagos, Nigeria",
            "summary": "Backend engineer who shipped payments infra and reduced latency by 40%.",
            "skills": ["Python", "Kubernetes", "PostgreSQL"],
            "experience": [
                {
                    "role": "Backend Engineer",
                    "org": "Acme",
                    "start": "2021",
                    "end": "2024",
                    "summary": ["Shipped the migration; cut p95 latency by 40%"],
                },
                {
                    "role": "SRE",
                    "org": "Beta",
                    "start": "2018",
                    "end": "2021",
                    "summary": ["Automated deploys for 30 services"],
                },
            ],
            "education": ["BSc Computer Science"],
            "languages": ["English"],
        }
    )


def weak_resume():
    """No contact details, no skills, no dates — every gap shows up."""
    return parse_resume({"name": "", "title": "Worker", "experience": [{"role": "Analyst"}]})


def test_weights_match_the_schema_and_sum_to_100():
    schema_categories = set(SCHEMA["properties"]["category_scores"]["properties"])
    assert set(CATEGORY_WEIGHTS) == schema_categories
    assert sum(CATEGORY_WEIGHTS.values()) == 100.0


def test_full_payload_validates_and_is_deterministic():
    resume = rich_resume()
    kwargs = {
        "job_title": "Backend Engineer",
        "job_description": "Python Kubernetes PostgreSQL. 5 years experience.",
        "job_location": "Lagos",
    }
    first = score_resume(resume, **kwargs).payload(resume_id="r-1", job_id="j-1")
    second = score_resume(rich_resume(), **kwargs).payload(resume_id="r-1", job_id="j-1")
    assert first == second  # deterministic ship layer
    validate(first, SCHEMA)
    assert first["resume_id"] == "r-1" and first["job_id"] == "j-1"
    assert first["parser_metadata"]["source_format"] == "json"


def test_every_category_present_bounded_and_overall_is_the_weighted_mean():
    report = score_resume(rich_resume(), job_title="Backend Engineer")
    assert set(report.category_scores) == set(CATEGORY_WEIGHTS)
    for name, score in report.category_scores.items():
        assert 0.0 <= score <= 100.0, name
    recomputed = (
        sum(report.category_scores[n] * CATEGORY_WEIGHTS[n] for n in CATEGORY_WEIGHTS) / 100.0
    )
    assert report.overall == round(recomputed, 1)
    assert 0.0 <= report.overall <= 100.0


def test_categories_the_posting_does_not_demand_score_full():
    report = score_resume(rich_resume(), job_description="Build things with Python.")
    assert report.category_scores["certifications_match"] == 100.0
    assert report.category_scores["language_match"] == 100.0
    assert report.category_scores["location_match"] == 100.0  # no location stated


def test_demanded_certification_without_listing_scores_zero_with_suggestion():
    report = score_resume(
        rich_resume(), job_description="Applicants must hold an active certification."
    )
    assert report.category_scores["certifications_match"] == 0.0
    hints = [s for s in report.suggestions if s["category"] == "certifications_match"]
    assert hints and "actually hold" in hints[0]["suggestion"]
    with_certs = parse_resume({"certifications": ["AWS Solutions Architect"]})
    report2 = score_resume(with_certs, job_description="certification required")
    assert report2.category_scores["certifications_match"] == 100.0


def test_language_demand_respects_honest_listings():
    no_lang = parse_resume({"name": "X"})
    report = score_resume(no_lang, job_description="Fluent English required.")
    assert report.category_scores["language_match"] == 0.0
    assert any(s["category"] == "language_match" for s in report.suggestions)
    with_lang = parse_resume({"name": "X", "languages": ["English"]})
    report2 = score_resume(with_lang, job_description="Fluent English required.")
    assert report2.category_scores["language_match"] == 100.0


def test_location_matching_city_region_mismatch_and_remote():
    resume = rich_resume()  # location: Lagos, Nigeria
    same_city = score_resume(resume, job_description="", job_location="Lagos")
    assert same_city.category_scores["location_match"] == 100.0
    same_region = score_resume(resume, job_description="", job_location="Abuja, Nigeria")
    assert same_region.category_scores["location_match"] == 70.0
    elsewhere = score_resume(resume, job_description="", job_location="Berlin, Germany")
    assert elsewhere.category_scores["location_match"] == 0.0
    assert any(s["category"] == "location_match" for s in elsewhere.suggestions)
    remote = score_resume(resume, job_description="Fully remote role", job_location="Berlin")
    assert remote.category_scores["location_match"] == 100.0


def test_years_experience_with_and_without_a_stated_requirement():
    # rich resume evidences 6 dated years (2018-2021, 2021-2024)
    met = score_resume(rich_resume(), job_description="Requires 5 years experience.")
    assert met.category_scores["years_experience"] == 100.0
    short = score_resume(rich_resume(), job_description="Requires 12 years experience.")
    assert short.category_scores["years_experience"] == pytest.approx(50.0)
    assert any(s["category"] == "years_experience" for s in short.suggestions)
    undated = parse_resume({"name": "X", "experience": [{"role": "Analyst"}]})
    no_req = score_resume(undated, job_description="Nothing about tenure.")
    assert no_req.category_scores["years_experience"] == 40.0
    assert any(
        "dated experience" in s["suggestion"]
        for s in no_req.suggestions
        if s["category"] == "years_experience"
    )


def test_skills_match_uses_the_resume_skills_section():
    resume = rich_resume()
    half = score_resume(resume, required=["python", "cobol"])
    assert half.category_scores["skills_match"] == 50.0
    assert any(s["category"] == "skills_match" for s in half.suggestions)
    empty = parse_resume({"name": "X", "title": "Dev"})
    zero = score_resume(empty, required=["python"])
    assert zero.category_scores["skills_match"] == 0.0
    none_required = score_resume(empty, required=[])
    assert none_required.category_scores["skills_match"] == 100.0


def test_education_demand_versus_listed_qualification():
    bsc = rich_resume()  # BSc Computer Science → level 2
    under = score_resume(bsc, job_description="Master's degree required.")
    assert under.category_scores["education_match"] == 50.0
    assert any(s["category"] == "education_match" for s in under.suggestions)
    absent = parse_resume({"name": "X"})
    zero = score_resume(absent, job_description="Bachelor's degree required.")
    assert zero.category_scores["education_match"] == 0.0
    msc = parse_resume({"name": "X", "education": ["MSc Data Science"]})
    assert (
        score_resume(msc, job_description="Master's degree required.").category_scores[
            "education_match"
        ]
        == 100.0
    )
    assert (
        score_resume(bsc, job_description="No schooling mentions.").category_scores[
            "education_match"
        ]
        == 100.0
    )


def test_employment_gaps_penalise_only_real_gaps():
    contiguous = score_resume(rich_resume())  # 2018→2021→2024, no gap
    assert contiguous.category_scores["employment_gaps"] == 100.0
    gappy = parse_resume(
        {
            "name": "X",
            "experience": [
                {"role": "A", "start": "2018", "end": "2019"},
                {"role": "B", "start": "2021", "end": "2024"},
            ],
        }
    )
    report = score_resume(gappy)
    assert report.category_scores["employment_gaps"] == 65.0
    assert any(s["category"] == "employment_gaps" for s in report.suggestions)
    undated = score_resume(parse_resume({"experience": [{"role": "A"}]}))
    assert undated.category_scores["employment_gaps"] == 100.0  # nothing to gap-check


def test_overall_impact_rewards_summary_quantification_and_verbs():
    rich = score_resume(rich_resume())
    assert rich.category_scores["overall_impact"] == 100.0
    bare = score_resume(parse_resume({"name": "X", "title": "Dev"}))
    assert bare.category_scores["overall_impact"] == 0.0
    assert any(s["category"] == "overall_impact" for s in bare.suggestions)


def test_contact_info_reports_every_missing_channel_once():
    partial = score_resume(parse_resume({"name": "Ada", "email": "a@b.co"}))
    assert partial.category_scores["contact_info"] == 55.0  # 40 email + 15 name
    hints = [s for s in partial.suggestions if s["category"] == "contact_info"]
    assert len(hints) == 1
    assert "phone number" in hints[0]["suggestion"] and "location" in hints[0]["suggestion"]


def test_job_title_match_finds_the_headline_wording_or_flags_it():
    aligned = score_resume(rich_resume(), job_title="Backend Engineer")
    assert aligned.category_scores["job_title_match"] == 100.0
    off = score_resume(rich_resume(), job_title="Blockchain Architect")
    assert off.category_scores["job_title_match"] < 100.0
    assert any(s["category"] == "job_title_match" for s in off.suggestions)
    no_title = score_resume(rich_resume(), job_title="")
    assert no_title.category_scores["job_title_match"] == 100.0  # no demand


def test_every_sub_100_category_ships_a_suggestion_with_a_valid_priority():
    report = score_resume(
        weak_resume(),
        job_title="Data Analyst",
        job_description="Master's degree, certification and fluent German required.",
        job_location="Berlin, Germany",
    )
    assert isinstance(report, ScoreReport)
    for name, score in report.category_scores.items():
        if score >= 100.0 or name == "keyword_match":
            continue
        hints = [s for s in report.suggestions if s["category"] == name]
        assert hints, f"{name} scored {score} but shipped no suggestion"
    for suggestion in report.suggestions:
        assert suggestion["priority"] in {"high", "medium", "low"}
        assert suggestion["category"] in CATEGORY_WEIGHTS
        assert suggestion["suggestion"]


def test_keyword_gaps_get_one_suggestion_per_missing_keyword():
    report = score_resume(rich_resume(), required=["python", "cobol", "fortran"])
    gap_hints = [s for s in report.suggestions if s["category"] == "keyword_match"]
    assert len(gap_hints) == 2  # cobol + fortran missing, python exact
    assert report.category_scores["keyword_match"] == pytest.approx(33.3)
    assert report.coverage == pytest.approx(0.3333, abs=0.001)
    assert sorted(report.missing) == ["cobol", "fortran"]
    validate(report.payload(), SCHEMA)


def test_no_keywords_required_means_full_keyword_score():
    report = score_resume(rich_resume(), required=[])
    assert report.category_scores["keyword_match"] == 100.0
    assert report.coverage == 1.0
    assert report.missing == []
