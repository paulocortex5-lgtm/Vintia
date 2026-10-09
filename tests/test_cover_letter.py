"""Cover letter generator tests (task 10.4) — facts only, schema-valid."""

import json
import re

import pytest

from engine.ats import parse_resume
from engine.errors import AllProvidersExhausted, SchemaValidationError
from engine.generators import generate_cover_letter
from engine.json_utils import load_json, validate
from engine.llm import LLMClient, LLMResult
from engine.sources.portals.base import JobListing

SCHEMA = load_json("engine/schemas/cover_letter.schema.json")

RESUME = {
    "name": "Ada Okafor",
    "title": "Backend Engineer",
    "email": "ada@example.com",
    "skills": ["PostgreSQL", "Kubernetes"],
    "education": ["BSc Computer Science, UNN (2020)"],
    "languages": ["English"],
    "experience": [
        {
            "role": "SRE",
            "org": "Acme Robotics Ltd",
            "start": "2021",
            "end": "2024",
            "summary": [
                "Shipped the payments migration; cut p95 latency by 40%",
                "Automated deploys for 30 services",
            ],
        }
    ],
}

LISTING = JobListing(
    portal="greenhouse",
    external_id="127817",
    title="Backend Engineer",
    company="Acme Robotics Ltd",
    location="London",
    url="https://job-boards.greenhouse.io/acme/jobs/127817",
    description="We need postgres and Kubernetes. 5 years experience.",
)

EMPTY_COMPANY_LISTING = JobListing(
    portal="greenhouse",
    external_id="9",
    title="Backend Engineer",
    company="",
    location="London",
    url="https://job-boards.greenhouse.io/acme/jobs/9",
    description="Python work.",
)


def _resume(profile=None):
    return parse_resume(profile if profile is not None else RESUME)


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


def _polish_json(resume_id: str = "MODEL") -> str:
    body = (
        "I am writing to apply for the Backend Engineer role. "
        "My experience maps onto your needs and I would welcome a conversation. "
    )
    return json.dumps(
        {
            "resume_id": resume_id,
            "job_id": resume_id,
            "content": body * 3,
            "sections": [{"heading": "Opening", "body": body, "word_count": 999}],
            "metadata": {
                "company_name": resume_id,
                "job_title": resume_id,
                "total_word_count": 999,
                "generated_at": "2020-01-01T00:00:00Z",
                "model": resume_id,
                "tone": "casual",
            },
        }
    )


def test_deterministic_letter_validates_and_follows_the_prompt_structure():
    artifact = generate_cover_letter(_resume(), LISTING, resume_id="cv-1")
    payload = artifact.payload
    validate(payload, SCHEMA)
    headings = [s["heading"] for s in payload["sections"]]
    assert headings[0] == "Opening" and headings[-1] == "Closing"
    assert "Achievement" in headings and "Fit" in headings
    assert len(payload["content"]) >= 100
    assert payload["metadata"]["total_word_count"] == len(payload["content"].split())
    assert payload["resume_id"] == "cv-1" and payload["job_id"] == "127817"
    assert artifact.provider == "deterministic" and artifact.polished is False


def test_every_number_and_fact_in_the_letter_comes_from_the_inputs():
    artifact = generate_cover_letter(_resume(), LISTING, resume_id="cv-2")
    content = artifact.payload["content"]
    assert "Acme Robotics Ltd" in content  # real employer from the posting
    assert "Backend Engineer" in content  # real job title
    # verbatim achievement bullets (quantified ones surface first)
    assert "cut p95 latency by 40%" in content
    assert "Automated deploys for 30 services" in content
    # no invented numbers: every digit in the letter exists in the inputs
    corpus = json.dumps(RESUME) + LISTING.description + LISTING.title + LISTING.company
    for number in re.findall(r"\d+", content):
        assert number in corpus, f"invented number in letter: {number}"
    assert "[Company]" not in content
    assert "@" not in content  # no contact block invented (signature is a name)


def test_empty_company_is_omitted_not_placeholdered():
    artifact = generate_cover_letter(_resume(), EMPTY_COMPANY_LISTING, resume_id="cv-3")
    payload = artifact.payload
    validate(payload, SCHEMA)
    assert payload["metadata"]["company_name"] == ""
    assert "at ." not in payload["content"]
    assert "Acme" not in payload["content"]


def test_no_experience_drops_the_achievement_section_rather_than_faking_one():
    bare = _resume({"name": "Ada", "title": "Dev", "skills": ["Python"], "email": "a@b.co"})
    artifact = generate_cover_letter(bare, LISTING, resume_id="cv-4")
    validate(artifact.payload, SCHEMA)
    headings = [s["heading"] for s in artifact.payload["sections"]]
    assert "Achievement" not in headings
    assert "latency" not in artifact.payload["content"]


def test_matched_keywords_use_the_resumes_own_spelling():
    artifact = generate_cover_letter(_resume(), LISTING, resume_id="cv-5")
    content = artifact.payload["content"]
    assert "PostgreSQL" in content  # not the posting's lowercased "postgres"
    assert "Kubernetes" in content
    keywords = artifact.payload["metadata"]["personalization_keywords_used"]
    assert keywords and all(isinstance(k, str) for k in keywords)


def test_tone_is_validated_and_invalid_tones_are_refused():
    artifact = generate_cover_letter(_resume(), LISTING, resume_id="cv-6", tone="formal")
    assert artifact.payload["metadata"]["tone"] == "formal"
    validate(artifact.payload, SCHEMA)
    with pytest.raises(SchemaValidationError):
        generate_cover_letter(_resume(), LISTING, tone="snarky")


def test_valid_model_output_replaces_the_letter_but_never_the_identity():
    client = _FakeClient(text=_polish_json())
    artifact = generate_cover_letter(
        _resume(), LISTING, resume_id="cv-7", client=client, chain=[("t", "m")]
    )
    assert artifact.polished and artifact.provider == "scripted"
    payload = artifact.payload
    assert payload["resume_id"] == "cv-7" and payload["job_id"] == "127817"  # ours
    meta = payload["metadata"]
    assert meta["company_name"] == "Acme Robotics Ltd"  # ours, not the model's
    assert meta["job_title"] == "Backend Engineer"
    assert meta["model"] == "scripted"
    assert meta["tone"] == "professional"  # the requested tone, not "casual"
    assert meta["total_word_count"] == len(payload["content"].split())  # recounted
    assert payload["sections"][0]["word_count"] == len(payload["sections"][0]["body"].split())
    validate(payload, SCHEMA)
    assert artifact.envelope
    sent = client.captured[0]["content"]
    assert "{{" not in sent and "}}" not in sent
    assert "cv-7" in sent and "Acme Robotics Ltd" in sent


def test_garbage_output_keeps_the_deterministic_letter():
    client = _FakeClient(text="not json at all")
    artifact = generate_cover_letter(_resume(), LISTING, client=client, chain=[("t", "m")])
    assert artifact.polished is False and artifact.provider == "deterministic"
    assert artifact.fallback is False
    validate(artifact.payload, SCHEMA)


def test_provider_failure_falls_back_and_dry_run_skips_polish():
    failing = _FakeClient(fail=True)
    artifact = generate_cover_letter(_resume(), LISTING, client=failing, chain=[("t", "m")])
    assert artifact.fallback is True and artifact.polished is False
    validate(artifact.payload, SCHEMA)

    dry = _FakeClient(text=_polish_json(), dry_run=True)
    artifact = generate_cover_letter(_resume(), LISTING, client=dry, chain=[("t", "m")])
    assert artifact.polished is False and artifact.fallback is False
    validate(artifact.payload, SCHEMA)
