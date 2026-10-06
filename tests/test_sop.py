"""SOP generator tests (task 3.2) — deterministic honesty + LLM polish paths."""

import json

import pytest

from engine.errors import AllProvidersExhausted, SchemaValidationError
from engine.generators import generate_sop
from engine.generators.resume import CandidateProfile, Education, Experience
from engine.json_utils import load_json, validate
from engine.llm import LLMClient, LLMResult
from engine.scholarships import get_scholarship

SCHEMA = load_json("engine/schemas/sop.schema.json")


def _profile(*, with_summary: bool = True) -> CandidateProfile:
    return CandidateProfile(
        name="Ada Okafor",
        title="Backend Engineer",
        summary="I build reliable systems and want to move into ML research."
        if with_summary
        else "",
        skills=("Python", "Kubernetes", "PostgreSQL"),
        experience=(Experience(role="SRE", org="Acme", start="2022", end="2026"),),
        education=(Education(degree="BSc Computer Science", school="UNN", year="2020"),),
        languages=("English",),
    )


def _valid_polish_json() -> str:
    return json.dumps(
        {
            "applicant_id": "MODEL-ECHO",
            "scholarship_id": "MODEL-ECHO",
            "content": "Polished statement of purpose body long enough to pass validation. " * 4,
            "sections": [
                {"heading": "Motivation", "body": "b1"},
                {"heading": "Background", "body": "b2"},
                {"heading": "Fit", "body": "b3"},
            ],
            "metadata": {"total_word_count": 40, "generated_at": "2026-10-06T00:00:00Z"},
        }
    )


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


def test_deterministic_sop_validates_and_covers_all_sections():
    sch = get_scholarship("chevening")
    artifact = generate_sop(_profile(), scholarship=sch, field_of_study="data science")
    validate(artifact.payload, SCHEMA)
    assert [s["heading"] for s in artifact.payload["sections"]] == [
        "Motivation",
        "Background",
        "Fit",
        "Career Goals",
        "Closing",
    ]
    assert artifact.provider == "deterministic" and artifact.polished is False
    assert artifact.envelope == {}  # no client → no envelope
    assert artifact.payload["scholarship_id"] == "chevening"


def test_sop_contains_only_supplied_facts():
    sch = get_scholarship("chevening")
    artifact = generate_sop(
        _profile(), scholarship=sch, field_of_study="data science", career_goal="Lead a team."
    )
    content = artifact.content
    assert "Acme" in content and "UNN" in content  # real experience/education
    assert sch.name in content  # real scholarship facts in Fit
    assert "Lead a team." in content  # caller's own goal
    assert "University of Oxford" not in content  # nothing invented


def test_empty_profile_gets_honest_placeholders_and_still_validates():
    empty = CandidateProfile(name="", title="")
    artifact = generate_sop(empty, scholarship=None, field_of_study="")
    validate(artifact.payload, SCHEMA)
    assert "does not yet contain a personal summary" in artifact.content
    assert "contains no experience or education entries yet" in artifact.content
    assert "No five-year career goal" in artifact.content


def test_invalid_tone_is_refused_by_the_schema():
    with pytest.raises(SchemaValidationError):
        generate_sop(_profile(), tone="sarcastic")


def test_valid_model_output_replaces_payload_but_never_identity():
    client = _FakeClient(text=_valid_polish_json())
    artifact = generate_sop(
        _profile(),
        scholarship=get_scholarship("chevening"),
        applicant_id="app-9",
        client=client,
        chain=[("t", "m")],
    )
    assert artifact.polished and artifact.provider == "scripted"
    assert artifact.payload["applicant_id"] == "app-9"  # ours, not MODEL-ECHO
    assert artifact.payload["scholarship_id"] == "chevening"
    assert client.captured and "{{ applicant_profile }}" not in str(client.captured)
    assert artifact.envelope  # client present → R24 envelope


def test_garbage_model_output_keeps_the_deterministic_payload():
    client = _FakeClient(text="not json at all")
    artifact = generate_sop(_profile(), client=client, chain=[("t", "m")])
    assert artifact.polished is False and artifact.provider == "deterministic"
    assert artifact.fallback is False  # not a provider failure — invalid output only


def test_provider_failure_falls_back_and_dry_run_skips_polish():
    failing = _FakeClient(fail=True)
    artifact = generate_sop(_profile(), client=failing, chain=[("t", "m")])
    assert artifact.fallback is True and artifact.polished is False
    validate(artifact.payload, SCHEMA)

    dry = _FakeClient(text=_valid_polish_json(), dry_run=True)
    artifact = generate_sop(_profile(), client=dry, chain=[("t", "m")])
    assert artifact.polished is False and artifact.fallback is False
    validate(artifact.payload, SCHEMA)


def test_prompt_rendering_leaves_no_template_tokens():
    client = _FakeClient(text="")
    generate_sop(
        _profile(),
        scholarship=get_scholarship("daad"),
        applicant_id="a1",
        target_program="MSc Data",
        client=client,
        chain=[("t", "m")],
    )
    sent = client.captured[0]["content"]
    assert "{{" not in sent and "}}" not in sent
    assert "Ada Okafor" in sent and "MSc Data" in sent
