"""CV improvement engine tests (task 10.2) — facts preserved, schema-valid."""

import json

from engine.ats import parse_resume
from engine.errors import AllProvidersExhausted
from engine.improve import improve_cv
from engine.json_utils import load_json, validate
from engine.llm import LLMClient, LLMResult

SCHEMA = load_json("engine/schemas/cv_improvement.schema.json")

PROFILE = {
    "name": "Ada Okafor",
    "title": "Backend Engineer",
    "email": "ada@example.com",
    "skills": ["Python"],
    "summary": "Backend engineer with six years in payments.",
    "experience": [
        {
            "role": "SRE",
            "org": "Acme Robotics Ltd",
            "start": "2021",
            "end": "2024",
            "summary": [
                "Worked on Kubernetes migrations in order to cut latency, etc.",
                "Automated deploys for 30 services",
            ],
        }
    ],
    "education": ["BSc Computer Science, UNN (2020)"],
}


def _resume(profile=None):
    return parse_resume(profile if profile is not None else PROFILE)


class _FakeClient(LLMClient):
    """Scripted run_chain: valid JSON / garbage / failure / dry-run."""

    def __init__(self, text: str = "", fail: bool = False, dry_run: bool = False):
        super().__init__()
        self.text = text
        self.fail = fail
        self.dry_run_result = dry_run
        self.captured: list = []

    def run_chain(self, chain, messages, **kwargs):
        self.captured = messages
        if self.fail:
            raise AllProvidersExhausted("all providers failed")
        return LLMResult(
            text=self.text,
            provider="scripted",
            model="scripted",
            tokens_in=5,
            tokens_out=5,
            cost_usd=0.0,
            dry_run=self.dry_run_result,
        )


def _polish_json(original_cv_id: str = "MODEL-ECHO") -> str:
    return json.dumps(
        {
            "original_cv_id": original_cv_id,
            "improvements": [
                {
                    "category": "metrics",
                    "section": "Professional Experience",
                    "original_text": "cut latency",
                    "improved_text": "cut p95 latency by 40%",
                    "reason": "model polish",
                    "impact": "high",
                    "priority": 9,
                },
                {
                    "category": "clarity",
                    "original_text": "in order to",
                    "improved_text": "to",
                    "reason": "filler",
                    "impact": "low",
                    "priority": 2,
                },
            ],
            "improved_cv": "Ada Okafor\n\n## Summary\nPolished summary body.",
            "summary": {
                "total_improvements": 99,
                "high_impact_count": 99,
                "medium_impact_count": 0,
                "low_impact_count": 99,
            },
        }
    )


def test_deterministic_payload_validates_and_summary_counts_match_the_list():
    artifact = improve_cv(_resume(), original_cv_id="cv-1")
    payload = artifact.payload
    validate(payload, SCHEMA)
    assert payload["original_cv_id"] == "cv-1"
    summary = payload["summary"]
    assert summary["total_improvements"] == len(payload["improvements"])
    assert summary["total_improvements"] <= 30
    impacts = [e["impact"] for e in payload["improvements"]]
    assert summary["high_impact_count"] == impacts.count("high")
    assert summary["medium_impact_count"] == impacts.count("medium")
    assert summary["low_impact_count"] == impacts.count("low")
    priorities = [e["priority"] for e in payload["improvements"]]
    assert priorities == sorted(priorities, reverse=True)  # ranked, as the prompt demands
    assert artifact.provider == "deterministic" and artifact.polished is False


def test_facts_are_never_changed_in_the_improved_cv():
    artifact = improve_cv(_resume(), original_cv_id="cv-1")
    text = artifact.improved_cv
    for fact in ("Ada Okafor", "Acme Robotics Ltd", "2021", "2024", "BSc Computer Science"):
        assert fact in text  # names, employers, dates, degrees untouched
    assert "30 services" in text  # real metric kept verbatim


def test_json_profile_gets_a_structure_entry_and_a_rendered_cv():
    artifact = improve_cv(_resume(), original_cv_id="cv-2")
    categories = [e["category"] for e in artifact.improvements]
    assert "structure" in categories
    text = artifact.improved_cv
    assert "## Experience" in text and "## Education" in text  # rendered from fields


def test_missing_sections_get_honest_placeholders_not_invented_text():
    artifact = improve_cv(
        _resume({"name": "X", "title": "Dev", "email": "x@y.co"}), original_cv_id="cv-3"
    )
    validate(artifact.payload, SCHEMA)
    placeholders = [e for e in artifact.improvements if e["category"] == "content"]
    assert {e["section"] for e in placeholders} == {"Summary", "Skills"}
    assert "no professional summary" in artifact.improved_cv.lower()
    assert "add 2-3 lines" in artifact.improved_cv  # a marker, never fake prose


def test_weak_verbs_and_filler_are_edits_the_applicant_can_review():
    artifact = improve_cv(_resume(), original_cv_id="cv-4")
    by_cat = {e["category"]: e for e in artifact.improvements}
    assert "action_verbs" in by_cat
    assert "Engineered" in by_cat["action_verbs"]["improved_text"]
    assert "clarity" in by_cat
    assert "to cut" in artifact.improved_cv
    assert "in order to" not in artifact.improved_cv
    assert "etc." not in artifact.improved_cv


def test_keyword_mirroring_never_invents_a_skill():
    # Kubernetes is evidenced in a bullet but missing from Skills → mirrored
    artifact = improve_cv(
        _resume(), original_cv_id="cv-5", job_description="Kubernetes Terraform experience"
    )
    validate(artifact.payload, SCHEMA)
    keyword_entries = [e for e in artifact.improvements if e["category"] == "keyword_optimization"]
    assert keyword_entries and "Kubernetes" in keyword_entries[0]["improved_text"]
    # Terraform appears nowhere in the resume → never added anywhere; the
    # honest channel for "missing keyword" is the ATS scan (9.x), not a
    # fabricated Skills entry
    assert "Terraform" not in artifact.improved_cv
    edited_text = " ".join(
        f"{e.get('original_text', '')} {e.get('improved_text', '')}" for e in artifact.improvements
    )
    assert "Terraform" not in edited_text  # not even as a suggested edit


def test_without_a_job_description_there_are_no_keyword_edits():
    artifact = improve_cv(_resume(), original_cv_id="cv-6")
    assert "keyword_optimization" not in {e["category"] for e in artifact.improvements}


def test_valid_model_output_replaces_the_payload_but_never_the_identity():
    client = _FakeClient(text=_polish_json())
    artifact = improve_cv(
        _resume(), original_cv_id="cv-7", client=client, chain=[("t", "m")], run_id="r1"
    )
    assert artifact.polished and artifact.provider == "scripted"
    assert artifact.payload["original_cv_id"] == "cv-7"  # ours, not MODEL-ECHO
    # the summary must recount the shipped list, never trust the model's counts
    assert artifact.payload["summary"]["total_improvements"] == 2
    assert artifact.payload["summary"]["high_impact_count"] == 1
    priorities = [e["priority"] for e in artifact.improvements]
    assert priorities == sorted(priorities, reverse=True)
    validate(artifact.payload, SCHEMA)
    assert artifact.envelope  # client present → R24 envelope
    sent = client.captured[0]["content"]
    assert "{{" not in sent and "}}" not in sent  # template fully rendered
    assert "cv-7" in sent and PROFILE["name"] in sent


def test_garbage_output_keeps_the_deterministic_payload():
    client = _FakeClient(text="not json at all")
    artifact = improve_cv(_resume(), client=client, chain=[("t", "m")])
    assert artifact.polished is False and artifact.provider == "deterministic"
    assert artifact.fallback is False  # invalid output ≠ provider failure
    validate(artifact.payload, SCHEMA)


def test_provider_failure_falls_back_and_dry_run_skips_polish():
    failing = _FakeClient(fail=True)
    artifact = improve_cv(_resume(), client=failing, chain=[("t", "m")])
    assert artifact.fallback is True and artifact.polished is False
    validate(artifact.payload, SCHEMA)

    dry = _FakeClient(text=_polish_json(), dry_run=True)
    artifact = improve_cv(_resume(), client=dry, chain=[("t", "m")])
    assert artifact.polished is False and artifact.fallback is False
    validate(artifact.payload, SCHEMA)


def test_improvements_are_capped_at_thirty():
    profile = dict(PROFILE, summary="")
    profile["experience"] = [
        {
            "role": "Dev",
            "org": f"Org{i}",
            "start": "2020",
            "end": "2021",
            "summary": [f"Worked on service {i} in order to ship it, etc."],
        }
        for i in range(40)
    ]
    artifact = improve_cv(_resume(profile), original_cv_id="cv-8")
    assert len(artifact.improvements) <= 30
    validate(artifact.payload, SCHEMA)
