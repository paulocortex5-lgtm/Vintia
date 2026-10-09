"""Cover letter generator (task 10.4) — deterministic-first, facts only.

Builds a schema-valid cover letter (``cover_letter.schema.json``) from a
parsed resume (9.1) plus the target :class:`JobListing`. The deterministic
ship layer writes from real facts only:

* **Opening** — the actual job title and employer (omitted when unknown),
  one concrete fit reason drawn from matched keywords;
* **Achievement** — up to two *verbatim* experience bullets (quantified
  ones first); when there are none, the section is dropped rather than
  padded — the generator never invents an achievement;
* **Fit** — matched keywords, the real qualification, real languages;
* **Closing** — a plain professional close; no fake availability, no fake
  contact details, no ``[Company]`` placeholders.

The optional LLM polish renders the shipped ``v1_cover_letter.md`` prompt;
model JSON must validate against the schema or the deterministic letter is
kept — and ``resume_id``/``job_id``/metadata identity always stay ours.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from ..ats.keywords import job_keywords, match_keywords
from ..ats.parser import ParsedResume
from ..errors import AllProvidersExhausted, SchemaValidationError, VantiaError
from ..json_utils import load_json, safe_parse, validate
from ..llm import LLMClient, LLMResult, build_envelope
from ..llm.client import is_dry_run
from ..logging_config import utc_now
from ..sources.portals.base import JobListing

__all__ = ["CoverLetterArtifact", "generate_cover_letter"]


def _schema() -> dict[str, Any]:
    schema = load_json("engine/schemas/cover_letter.schema.json")
    if schema is None:  # pragma: no cover — packaged file must exist
        raise VantiaError("cover_letter.schema.json missing", code="schema_missing")
    return schema


def _prompt() -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", "v1_cover_letter.md")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _words(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def _section(heading: str, body: str) -> dict[str, Any]:
    clean = body.strip()
    return {"heading": heading, "body": clean, "word_count": _words(clean)}


@dataclass
class CoverLetterArtifact:
    """One cover letter: payload + provenance (mirrors ``SopArtifact``)."""

    payload: dict[str, Any]
    provider: str = "deterministic"
    polished: bool = False
    fallback: bool = False
    envelope: dict[str, Any] = field(default_factory=dict)

    @property
    def content(self) -> str:
        return str(self.payload.get("content", ""))

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload": self.payload,
            "content": self.content,
            "provider": self.provider,
            "polished": self.polished,
            "fallback": self.fallback,
            "envelope": self.envelope,
        }


def _surface_forms(matched: list[str], skills: list[str]) -> list[str]:
    """Spell each matched keyword the way the resume spells it (job wording
    is normalised to lowercase; a letter should say ``PostgreSQL``, not
    ``postgresql``). Falls back to the job's wording when the resume has no
    surface form of its own."""
    out: list[str] = []
    for keyword in matched:
        surface = next((s for s in skills if match_keywords([keyword], [s])[0]), keyword)
        out.append(surface)
    return out


def _deterministic(
    resume: ParsedResume,
    listing: JobListing,
    *,
    resume_id: str,
    job_id: str,
    tone: str,
    language: str,
) -> dict[str, Any]:
    """A letter built only from the resume's facts and the posting's facts."""
    company = (listing.company or "").strip()
    job_title = (listing.title or "").strip()
    required = job_keywords(listing.description, title=job_title)
    matched, _missing, _how = match_keywords(required, list(resume.skills))
    used = _surface_forms(matched[:3], list(resume.skills))

    sections: list[dict[str, Any]] = []

    # Opening — role/company stated exactly; no placeholder company
    if company:
        opening = f"I am writing to apply for the {job_title} at {company}."
    else:
        opening = f"I am writing to apply for the {job_title}."
    if used:
        opening += (
            f" My hands-on experience with {', '.join(used)} maps directly onto "
            "what the role asks for."
        )
    elif resume.title:
        opening += (
            f" My background as a {resume.title} maps onto the responsibilities "
            "described in the posting."
        )
    sections.append(_section("Opening", opening))

    # Achievement — verbatim bullets only, quantified first; none → no section
    experience_bullets = [
        str(b) for entry in resume.experience for b in entry.get("summary", []) or []
    ]
    quantified = [b for b in experience_bullets if re.search(r"\d", b)]
    plain = [b for b in experience_bullets if b not in quantified]
    picks = (quantified + plain)[:2]
    if picks:
        body = (
            "One highlight from my experience: "
            if len(picks) == 1
            else "Two highlights from my experience: "
        )
        cleaned = [b.rstrip(".;, ") for b in picks]
        body += ". ".join(cleaned) + "."
        sections.append(_section("Achievement", body))

    # Fit — only claims the resume actually supports
    fit_parts: list[str] = []
    if len(used) >= 2:
        fit_parts.append(
            f"The role calls for {', '.join(used)} and my CV evidences each of them "
            "directly in my experience."
        )
    if resume.education:
        degree = str(resume.education[0].get("degree", "")).strip()
        if degree:
            fit_parts.append(f"My qualifications include {degree}.")
    if resume.languages:
        fit_parts.append(f"My working languages include {', '.join(resume.languages)}.")
    if fit_parts:
        sections.append(_section("Fit", " ".join(fit_parts)))

    # Closing — no invented availability or contact details
    closing = "I would welcome the opportunity to discuss how my experience fits "
    closing += f"this role{' at ' + company if company else ''}. I look forward to your response."
    if resume.name:
        closing += f"\n\n{resume.name}"
    sections.append(_section("Closing", closing))

    content = "\n\n".join(f"{s['heading']}\n{s['body']}" for s in sections)
    payload: dict[str, Any] = {
        "resume_id": resume_id,
        "job_id": job_id,
        "content": content,
        "sections": sections,
        "metadata": {
            "company_name": company,
            "job_title": job_title,
            "total_word_count": _words(content),
            "generated_at": utc_now(),
            "model": "deterministic",
            "tone": tone,
            "personalization_keywords_used": _surface_forms(matched[:8], list(resume.skills)),
        },
    }
    validate(payload, _schema())
    return payload


# ── Optional LLM polish (schema-validated, identity fields stay ours) ─────


def _render_prompt(
    resume: ParsedResume,
    listing: JobListing,
    *,
    resume_id: str,
    job_id: str,
    tone: str,
    language: str,
) -> str:
    """Fill the shipped v1_cover_letter.md template (DATA, not instructions)."""
    text = _prompt()
    body = resume.raw_text.strip() or json.dumps(resume.to_dict(), ensure_ascii=False, indent=2)
    replacements = {
        "{{ resume }}": body,
        "{{ job_description }}": listing.description,
        "{{ job_url }}": listing.url,
        "{{ company_name }}": (listing.company or "").strip(),
        "{{ job_title }}": (listing.title or "").strip(),
        "{{ country }}": listing.country,
        "{{ language }}": language,
        "{{ tone }}": tone,
        "{{ resume_id }}": resume_id,
        "{{ job_id }}": job_id,
    }
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def _polish(
    payload: dict[str, Any],
    resume: ParsedResume,
    listing: JobListing,
    *,
    resume_id: str,
    job_id: str,
    tone: str,
    language: str,
    client: LLMClient,
    chain: list,
    run_id: str,
) -> tuple[dict[str, Any] | None, str]:
    """Model JSON → schema-valid letter; anything else keeps ours."""
    rendered = _render_prompt(
        resume,
        listing,
        resume_id=resume_id,
        job_id=job_id,
        tone=tone,
        language=language,
    )
    result = client.run_chain(
        chain,
        [{"role": "user", "content": rendered}],
        system="You are a senior recruiter. Output only JSON matching the schema.",
        temperature=0.0,
        run_id=run_id,
    )
    if result.dry_run:
        return None, result.provider
    try:
        parsed = safe_parse(result.text)
    except SchemaValidationError:
        return None, result.provider
    if not isinstance(parsed, dict):
        return None, result.provider
    try:
        validate(parsed, _schema())
    except SchemaValidationError:
        return None, result.provider
    # identity + metadata honesty: ours, recounted from the shipped content
    parsed["resume_id"] = resume_id
    parsed["job_id"] = job_id
    content = str(parsed.get("content", ""))
    parsed["metadata"] = {
        "company_name": (listing.company or "").strip(),
        "job_title": (listing.title or "").strip(),
        "total_word_count": _words(content),
        "generated_at": utc_now(),
        "model": result.provider,
        "tone": tone,
        "personalization_keywords_used": list(
            payload.get("metadata", {}).get("personalization_keywords_used", [])
        ),
    }
    for item in parsed.get("sections") or []:
        if isinstance(item, dict) and isinstance(item.get("body"), str):
            item["word_count"] = _words(item["body"])
    return parsed, result.provider


def generate_cover_letter(
    resume: ParsedResume,
    listing: JobListing,
    *,
    resume_id: str = "",
    tone: str = "professional",
    language: str = "en",
    client: LLMClient | None = None,
    chain: list | None = None,
    run_id: str = "0",
) -> CoverLetterArtifact:
    """Schema-valid cover letter for ``resume`` against ``listing``."""
    job_id = listing.external_id or listing.url
    payload = _deterministic(
        resume,
        listing,
        resume_id=resume_id,
        job_id=job_id,
        tone=tone,
        language=language,
    )
    provider, polished, fallback = "deterministic", False, False
    if client is not None and chain:
        try:
            polished_payload, used = _polish(
                payload,
                resume,
                listing,
                resume_id=resume_id,
                job_id=job_id,
                tone=tone,
                language=language,
                client=client,
                chain=chain,
                run_id=run_id,
            )
        except AllProvidersExhausted:
            polished_payload, used = None, provider
            fallback = True
        if polished_payload is not None:
            payload, provider, polished = polished_payload, used, True

    envelope: dict[str, Any] = {}
    if client is not None:
        digest = hashlib.sha256(resume.raw_text.encode("utf-8")).hexdigest()[:16]
        key = hashlib.sha256(f"cover|{resume_id}|{job_id}|{digest}".encode()).hexdigest()[:32]
        envelope = build_envelope(
            payload,
            LLMResult(
                text=str(payload.get("content", "")),
                provider=provider,
                model="",
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                dry_run=is_dry_run(None),
            ),
            task_id="10.4",
            run_id=run_id,
            prompt_version="v1",
            idempotency_key=key,
        )
    return CoverLetterArtifact(
        payload=payload,
        provider=provider,
        polished=polished,
        fallback=fallback,
        envelope=envelope,
    )
