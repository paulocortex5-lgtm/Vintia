"""Statement of Purpose generator (task 3.2).

Deterministic-first (repo pattern): the ship layer composes a
schema-valid SOP **only** from the applicant's profile, the target
scholarship's real facts and the caller's own inputs — it never
invents employers, dates or motivations. Missing material becomes an
explicit, honest placeholder line rather than filler prose.

Optional LLM polish renders the shipped ``v1_sop.md`` prompt; the
model's JSON must validate against ``sop.schema.json`` or the
deterministic payload is kept (``fallback=True``).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field

from ..errors import AllProvidersExhausted, SchemaValidationError, VantiaError
from ..json_utils import load_json, safe_parse, validate
from ..llm import LLMClient, LLMResult, build_envelope
from ..llm.client import is_dry_run
from ..logging_config import utc_now
from ..scholarships.database import Scholarship
from .resume import CandidateProfile

__all__ = ["SopArtifact", "generate_sop"]

_NO_SUMMARY = (
    "The profile does not yet contain a personal summary; add one to turn this "
    "section into the applicant's own motivation."
)
_NO_BACKGROUND = "The profile contains no experience or education entries yet."
_NO_GOAL = (
    "No five-year career goal was supplied with this request; add one to turn "
    "this section into a concrete direction."
)


@dataclass
class SopArtifact:
    payload: dict[str, object]
    provider: str = "deterministic"
    polished: bool = False
    fallback: bool = False
    envelope: dict[str, object] = field(default_factory=dict)

    @property
    def content(self) -> str:
        return str(self.payload.get("content", ""))

    def to_dict(self) -> dict[str, object]:
        return {
            "payload": self.payload,
            "content": self.content,
            "provider": self.provider,
            "polished": self.polished,
            "fallback": self.fallback,
            "envelope": self.envelope,
        }


def _schema() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "schemas", "sop.schema.json")
    schema = load_json(path)
    if schema is None:  # pragma: no cover — packaged file must exist
        raise VantiaError("sop.schema.json missing", code="schema_missing")
    return schema


def _prompt() -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", "v1_sop.md")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _words(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def _section(heading: str, body: str) -> dict[str, object]:
    return {"heading": heading, "body": body.strip(), "word_count": _words(body)}


def _background(candidate: CandidateProfile) -> str:
    lines: list[str] = []
    for exp in candidate.experience:
        span = " – ".join(part for part in (exp.start, exp.end) if part)
        header = f"{exp.role}, {exp.org}" + (f" ({span})" if span else "")
        lines.append(f"- {header}")
        lines.extend(f"  - {detail}" for detail in exp.summary)
    for edu in candidate.education:
        year = f" ({edu.year})" if edu.year else ""
        lines.append(f"- {edu.degree}, {edu.school}{year}")
    if candidate.skills:
        lines.append(f"- Skills: {', '.join(candidate.skills)}")
    if candidate.languages:
        lines.append(f"- Languages: {', '.join(candidate.languages)}")
    return "\n".join(lines) if lines else _NO_BACKGROUND


def _fit(scholarship: Scholarship | None, field_of_study: str, target_program: str) -> str:
    parts: list[str] = []
    if scholarship is not None:
        hosts = ", ".join(sorted(scholarship.host_countries))
        parts.append(
            f"This application targets the {scholarship.name}, offered by "
            f"{scholarship.provider} (study destinations: {hosts})."
        )
        if scholarship.funding == "varies":
            parts.append("Funding terms vary by programme and are confirmed with the provider.")
    if target_program:
        parts.append(f"Target programme: {target_program}.")
    if field_of_study:
        parts.append(f"Field of study: {field_of_study}.")
    if not parts:
        parts.append(
            "No programme or scholarship was supplied with this request; state the "
            "target explicitly to strengthen this section."
        )
    return " ".join(parts)


def _deterministic(
    candidate: CandidateProfile,
    *,
    scholarship: Scholarship | None,
    field_of_study: str,
    career_goal: str,
    target_program: str,
    applicant_id: str,
    tone: str,
    language: str,
) -> dict[str, object]:
    sections = [
        _section("Motivation", candidate.summary or _NO_SUMMARY),
        _section("Background", _background(candidate)),
        _section("Fit", _fit(scholarship, field_of_study, target_program)),
        _section("Career Goals", career_goal or _NO_GOAL),
        _section(
            "Closing",
            "The applicant requests consideration for "
            f"{scholarship.name if scholarship else (target_program or 'the programme')} "
            "and can supply supporting documents on request.",
        ),
    ]
    content = "\n\n".join(f"{s['heading']}\n{s['body']}" for s in sections)
    payload: dict[str, object] = {
        "applicant_id": applicant_id,
        "program_id": "",
        "scholarship_id": scholarship.id if scholarship else "",
        "content": content,
        "sections": sections,
        "metadata": {
            "total_word_count": _words(content),
            "generated_at": utc_now(),
            "model": "deterministic-v1",
            "tone": tone,
            "target_program": target_program,
            "target_scholarship": scholarship.name if scholarship else "",
            "language": language,
        },
    }
    validate(payload, _schema())
    return payload


def _render_prompt(
    candidate: CandidateProfile,
    *,
    scholarship: Scholarship | None,
    field_of_study: str,
    career_goal: str,
    target_program: str,
    applicant_id: str,
    tone: str,
    language: str,
    country: str,
) -> str:
    """Fill the shipped v1_sop.md template (DATA, not instructions)."""
    profile = {
        "name": candidate.name,
        "title": candidate.title,
        "summary": candidate.summary,
        "skills": list(candidate.skills),
        "languages": list(candidate.languages),
        "career_goal": career_goal,
        "field_of_study": field_of_study,
    }
    resume = {
        "experience": [
            {
                "role": e.role,
                "org": e.org,
                "start": e.start,
                "end": e.end,
                "summary": list(e.summary),
            }
            for e in candidate.experience
        ],
        "education": [
            {"degree": e.degree, "school": e.school, "year": e.year} for e in candidate.education
        ],
    }
    hosts = scholarship.host_countries if scholarship else ()
    replacements = {
        "{{ applicant_profile }}": json.dumps(profile, ensure_ascii=False),
        "{{ resume }}": json.dumps(resume, ensure_ascii=False),
        "{{ target_program }}": target_program,
        "{{ scholarship }}": scholarship.name if scholarship else "",
        "{{ country }}": country or (hosts[0] if hosts else ""),
        "{{ language }}": language,
        "{{ tone }}": tone,
        "{{ applicant_id }}": applicant_id,
        "{{ program_id }}": target_program,
        "{{ scholarship_id }}": scholarship.id if scholarship else "",
    }
    text = _prompt()
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def _polish(
    payload: dict[str, object],
    candidate: CandidateProfile,
    *,
    scholarship: Scholarship | None,
    field_of_study: str,
    career_goal: str,
    target_program: str,
    applicant_id: str,
    tone: str,
    language: str,
    country: str,
    client: LLMClient,
    chain: list,
    run_id: str,
) -> tuple[dict[str, object] | None, str]:
    """LLM rewrite; ``None`` keeps the deterministic payload (dry-run/invalid)."""
    rendered = _render_prompt(
        candidate,
        scholarship=scholarship,
        field_of_study=field_of_study,
        career_goal=career_goal,
        target_program=target_program,
        applicant_id=applicant_id,
        tone=tone,
        language=language,
        country=country,
    )
    result = client.run_chain(
        chain,
        [{"role": "user", "content": rendered}],
        system="You are an admissions writer. Output only JSON matching the schema.",
        temperature=0.0,
        run_id=run_id,
    )
    if result.dry_run:
        return None, result.provider
    try:
        parsed = safe_parse(result.text)
    except SchemaValidationError:
        return None, result.provider  # unparseable output keeps the deterministic payload
    if not isinstance(parsed, dict):
        return None, result.provider
    try:
        validate(parsed, _schema())
    except SchemaValidationError:
        return None, result.provider  # bad model output never replaces a valid payload
    # identity fields are ours, never the model's echo
    parsed["applicant_id"] = payload["applicant_id"]
    parsed["scholarship_id"] = payload["scholarship_id"]
    return parsed, result.provider


def generate_sop(
    candidate: CandidateProfile,
    *,
    scholarship: Scholarship | None = None,
    field_of_study: str = "",
    career_goal: str = "",
    target_program: str = "",
    applicant_id: str = "",
    country: str = "",
    tone: str = "professional",
    language: str = "en",
    client: LLMClient | None = None,
    chain: list | None = None,
    run_id: str = "0",
) -> SopArtifact:
    """Schema-valid SOP for ``candidate`` — deterministic ship layer first."""
    payload = _deterministic(
        candidate,
        scholarship=scholarship,
        field_of_study=field_of_study,
        career_goal=career_goal,
        target_program=target_program,
        applicant_id=applicant_id,
        tone=tone,
        language=language,
    )
    provider = "deterministic"
    polished = False
    fallback = False
    if client is not None and chain:
        try:
            polished_payload, used = _polish(
                payload,
                candidate,
                scholarship=scholarship,
                field_of_study=field_of_study,
                career_goal=career_goal,
                target_program=target_program,
                applicant_id=applicant_id,
                tone=tone,
                language=language,
                country=country,
                client=client,
                chain=chain,
                run_id=run_id,
            )
        except AllProvidersExhausted:
            polished_payload, used = None, provider
            fallback = True
        if polished_payload is not None:
            payload, provider, polished = polished_payload, used, True

    envelope: dict[str, object] = {}
    if client is not None:
        key = hashlib.sha256(
            f"sop|{applicant_id}|{scholarship.id if scholarship else ''}|{field_of_study}".encode()
        ).hexdigest()[:32]
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
            task_id="3.2",
            run_id=run_id,
            prompt_version="v1",
            idempotency_key=key,
        )
    return SopArtifact(
        payload=payload,
        provider=provider,
        polished=polished,
        fallback=fallback,
        envelope=envelope,
    )
