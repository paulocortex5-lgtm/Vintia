"""Research proposal generator tests (task 3.3)."""

import json

import pytest

from engine.errors import AllProvidersExhausted, VantiaError
from engine.generators import generate_proposal
from engine.generators.resume import CandidateProfile, Education, Experience
from engine.json_utils import load_json, validate
from engine.llm import LLMClient, LLMResult

SCHEMA = load_json("engine/schemas/research_proposal.schema.json")


def _profile() -> CandidateProfile:
    return CandidateProfile(
        name="Ada Okafor",
        title="Backend Engineer",
        summary="Moving into applied ML research.",
        skills=("Python", "Torch", "Kubernetes"),
        experience=(Experience(role="SRE", org="Acme", start="2022", end="2026"),),
        education=(Education(degree="BSc Computer Science", school="UNN", year="2020"),),
    )


class _FakeClient(LLMClient):
    def __init__(self, text: str = "", fail: bool = False):
        super().__init__()
        self.text = text
        self.fail = fail
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
            dry_run=False,
        )


def test_proposal_validates_and_is_grounded_in_real_inputs():
    artifact = generate_proposal(
        _profile(),
        field_of_study="machine learning",
        research_interests="efficient models on limited data",
        career_goal="Lead applied ML research at home.",
        target_program="MSc Data Science",
        funding_body="Some Fund",
        applicant_id="app-1",
    )
    validate(artifact.payload, SCHEMA)
    payload = artifact.payload
    assert payload["title"].startswith("An investigation into machine learning")
    assert "efficient models" in payload["research_question"]
    assert 3 <= len(payload["keywords"]) <= 10
    assert "python" in payload["keywords"]  # skills are real index terms
    assert "Acme" in artifact.content  # background from the profile only
    assert payload["metadata"]["degree_level"] == "MSc"
    assert artifact.provider == "deterministic"


def test_timeline_is_bounded_and_positive():
    artifact = generate_proposal(
        _profile(), field_of_study="robotics", research_interests="control"
    )
    timeline = artifact.payload["timeline"]
    assert len(timeline) >= 1
    total = 0
    for phase in timeline:
        months = phase["duration_months"]
        assert isinstance(months, int) and 1 <= months <= 48
        total += months
    assert total <= 48


def test_insufficient_real_terms_refuse_instead_of_faking_keywords():
    sparse = CandidateProfile(name="X", title="")
    with pytest.raises(VantiaError) as excinfo:
        generate_proposal(sparse, field_of_study="ai", research_interests="", career_goal="")
    assert excinfo.value.code == "proposal_keywords_insufficient"


def test_empty_motivation_gets_an_honest_placeholder():
    artifact = generate_proposal(
        _profile(), field_of_study="hci", research_interests="accessibility"
    )
    validate(artifact.payload, SCHEMA)
    assert "No career goal or research motivation was supplied" in artifact.content


def test_model_polish_replaces_payload_and_failure_falls_back():
    polished_json = json.dumps(
        {
            "applicant_id": "MODEL",
            "title": "A polished title about machine learning systems",
            "research_question": "A polished question long enough for the schema floor of 20 chars?",
            "abstract": "A polished abstract that easily clears the fifty character minimum floor.",
            "content": "Polished content. " * 30,
            "keywords": ["polished", "keywords", "trio"],
            "sections": [
                {"heading": "Background", "body": "x"},
                {"heading": "Methodology", "body": "y"},
                {"heading": "Impact", "body": "z"},
            ],
            "metadata": {"total_word_count": 60, "generated_at": "2026-10-06T00:00:00Z"},
        }
    )
    client = _FakeClient(text=polished_json)
    artifact = generate_proposal(
        _profile(),
        field_of_study="ml",
        research_interests="trustworthy models",
        applicant_id="app-7",
        client=client,
        chain=[("t", "m")],
    )
    assert artifact.polished and artifact.provider == "scripted"
    assert artifact.payload["applicant_id"] == "app-7"  # identity stays ours
    assert artifact.envelope

    failing = _FakeClient(fail=True)
    artifact = generate_proposal(
        _profile(),
        field_of_study="ml",
        research_interests="trustworthy models",
        client=failing,
        chain=[("t", "m")],
    )
    assert artifact.fallback and not artifact.polished
    validate(artifact.payload, SCHEMA)


def test_prompt_rendering_leaves_no_template_tokens():
    client = _FakeClient(text="")
    generate_proposal(
        _profile(),
        field_of_study="nlp",
        research_interests="low resource languages",
        funding_body="Fund X",
        supervisor="Prof. Y",
        client=client,
        chain=[("t", "m")],
    )
    sent = client.captured[0]["content"]
    assert "{{" not in sent and "}}" not in sent
    assert "low resource languages" in sent and "Prof. Y" in sent
