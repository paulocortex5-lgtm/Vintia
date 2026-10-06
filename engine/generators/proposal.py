"""Research proposal generator (task 3.3).

Deterministic-first like every generator: the proposal is composed from
the applicant's profile, the caller's research interests/field and a
fixed, honest timeline — no invented publications, supervisors,
datasets or results (the shipped ``v1_research_proposal.md`` prompt
carries the same constraints for the LLM path).

Keywords are derived from real inputs only; when those inputs cannot
yield the schema's minimum of three, the generator refuses
(``proposal_keywords_insufficient``) instead of padding with fake
index terms.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field

from ..errors import AllProvidersExhausted, SchemaValidationError, VantiaError
from ..json_utils import load_json, safe_parse, validate
from ..llm import LLMClient, LLMResult, build_envelope
from ..llm.client import is_dry_run
from ..logging_config import utc_now
from .resume import SKILL_STOPWORDS, CandidateProfile

__all__ = ["ProposalArtifact", "generate_proposal"]

#: default 12-month plan; every phase is a positive number of months (schema)
_DEFAULT_TIMELINE: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    ("Literature review", 3, ("Existing work mapped and gaps named",)),
    ("Research design", 2, ("Method, data source and success criteria fixed",)),
    ("Study execution", 4, ("Primary evidence collected and checked",)),
    ("Analysis and write-up", 3, ("Findings written up with limitations stated",)),
)

_NO_MOTIVATION = (
    "No career goal or research motivation was supplied with this request; add "
    "one to turn this section into the applicant's own case."
)
_TOKEN = re.compile(r"[^a-z0-9+#.]+")


@dataclass
class ProposalArtifact:
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
    path = os.path.join(os.path.dirname(__file__), "..", "schemas", "research_proposal.schema.json")
    schema = load_json(path)
    if schema is None:  # pragma: no cover — packaged file must exist
        raise VantiaError("research_proposal.schema.json missing", code="schema_missing")
    return schema


def _prompt() -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", "v1_research_proposal.md")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _words(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def _section(heading: str, body: str) -> dict[str, object]:
    return {"heading": heading, "body": body.strip(), "word_count": _words(body)}


def _keywords(field_of_study: str, research_interests: str, skills: tuple[str, ...]) -> list[str]:
    """3–10 index terms drawn only from real inputs (schema minItems=3)."""
    source = " ".join((field_of_study, research_interests, " ".join(skills)))
    seen: list[str] = []
    for token in _TOKEN.split(source.casefold()):
        token = token.strip(".#")
        if len(token) < 3 or token in SKILL_STOPWORDS or token.isdigit():
            continue
        if token not in seen:
            seen.append(token)
        if len(seen) == 10:
            break
    if len(seen) < 3:
        raise VantiaError(
            "cannot derive the schema's minimum 3 keywords from the supplied "
            "field, research interests and skills — provide more detail",
            code="proposal_keywords_insufficient",
            found=seen,
        )
    return seen


def _area(field_of_study: str, research_interests: str) -> str:
    if field_of_study.strip():
        return field_of_study.strip().rstrip(".")
    cleaned = " ".join(research_interests.split()).rstrip(".")
    if cleaned:
        return " ".join(cleaned.split()[:10])
    return "the proposed research area"


def _background(candidate: CandidateProfile, area: str) -> str:
    lines: list[str] = [f"Research area: {area}."]
    for edu in candidate.education:
        year = f" ({edu.year})" if edu.year else ""
        lines.append(f"- Education: {edu.degree}, {edu.school}{year}")
    for exp in candidate.experience:
        span = " – ".join(part for part in (exp.start, exp.end) if part)
        lines.append(f"- Experience: {exp.role}, {exp.org}" + (f" ({span})" if span else ""))
    if candidate.skills:
        lines.append(f"- Competencies: {', '.join(candidate.skills)}")
    return "\n".join(lines)


def _timeline() -> list[dict[str, object]]:
    return [
        {"phase": phase, "duration_months": months, "milestones": list(milestones)}
        for phase, months, milestones in _DEFAULT_TIMELINE
    ]


def _deterministic(
    candidate: CandidateProfile,
    *,
    field_of_study: str,
    research_interests: str,
    career_goal: str,
    target_program: str,
    funding_body: str,
    applicant_id: str,
    degree_level: str,
    language: str,
) -> dict[str, object]:
    area = _area(field_of_study, research_interests)
    question_area = " ".join(research_interests.split()).rstrip(".") or area
    keywords = _keywords(field_of_study, research_interests, candidate.skills)
    skills_phrase = ", ".join(candidate.skills[:3]) or "the competencies recorded in the profile"
    title = f"An investigation into {area}"
    question = (
        f"What approaches best advance {question_area}, and how can their effectiveness be "
        "evaluated with the resources available to the applicant?"
    )
    abstract = (
        f"This proposal sets out a feasible {degree_level} research plan in {area}. "
        f"It connects the applicant's existing competencies ({skills_phrase}) to a single "
        "answerable question, sets a month-by-month timeline with defined milestones, and "
        "states how progress and failure will be detected. The scope is bounded to what "
        "one postgraduate researcher can complete."
    )
    methodology = (
        f"Method: a staged approach to {area} — establish what is already known, work with "
        "material the applicant can access, evaluate results against the research question, "
        "and record failure criteria at each stage. Tools named in the profile are the "
        "starting point; no external dataset or collaborator is assumed."
    )
    sections = [
        _section("Background", _background(candidate, area)),
        _section("Motivation", career_goal or _NO_MOTIVATION),
        _section("Methodology", methodology),
        _section(
            "Timeline",
            "\n".join(
                f"- {phase} ({months} months): {'; '.join(milestones)}"
                for phase, months, milestones in _DEFAULT_TIMELINE
            ),
        ),
        _section(
            "Impact",
            f"On completion the applicant delivers the {degree_level} project in {area} "
            "described above — the written proposal, the executed study and its "
            "limitations — and returns the skills to their home context.",
        ),
    ]
    content = "\n\n".join(f"{s['heading']}\n{s['body']}" for s in sections)
    payload: dict[str, object] = {
        "applicant_id": applicant_id,
        "program_id": target_program,
        "title": title,
        "research_question": question,
        "abstract": abstract,
        "content": content,
        "keywords": keywords,
        "methodology": methodology,
        "timeline": _timeline(),
        "sections": sections,
        "metadata": {
            "total_word_count": _words(content),
            "generated_at": utc_now(),
            "model": "deterministic-v1",
            "degree_level": degree_level,
            "target_program": target_program,
            "funding_body": funding_body,
            "language": language,
        },
    }
    validate(payload, _schema())
    return payload


def _render_prompt(
    candidate: CandidateProfile,
    *,
    field_of_study: str,
    research_interests: str,
    career_goal: str,
    target_program: str,
    funding_body: str,
    applicant_id: str,
    supervisor: str,
    language: str,
) -> str:
    """Fill the shipped v1_research_proposal.md template (DATA, not instructions)."""
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
            {"role": e.role, "org": e.org, "start": e.start, "end": e.end}
            for e in candidate.experience
        ],
        "education": [
            {"degree": e.degree, "school": e.school, "year": e.year} for e in candidate.education
        ],
    }
    replacements = {
        "{{ applicant_profile }}": json.dumps(profile, ensure_ascii=False),
        "{{ resume }}": json.dumps(resume, ensure_ascii=False),
        "{{ research_interests }}": research_interests,
        "{{ target_program }}": target_program,
        "{{ supervisor }}": supervisor,
        "{{ funding_body }}": funding_body,
        "{{ language }}": language,
        "{{ applicant_id }}": applicant_id,
        "{{ program_id }}": target_program,
    }
    text = _prompt()
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def _polish(
    payload: dict[str, object],
    candidate: CandidateProfile,
    *,
    field_of_study: str,
    research_interests: str,
    career_goal: str,
    target_program: str,
    funding_body: str,
    applicant_id: str,
    supervisor: str,
    language: str,
    client: LLMClient,
    chain: list,
    run_id: str,
) -> tuple[dict[str, object] | None, str]:
    """LLM rewrite; ``None`` keeps the deterministic payload (dry-run/invalid)."""
    rendered = _render_prompt(
        candidate,
        field_of_study=field_of_study,
        research_interests=research_interests,
        career_goal=career_goal,
        target_program=target_program,
        funding_body=funding_body,
        applicant_id=applicant_id,
        supervisor=supervisor,
        language=language,
    )
    result = client.run_chain(
        chain,
        [{"role": "user", "content": rendered}],
        system="You are a research supervisor. Output only JSON matching the schema.",
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
    parsed["applicant_id"] = payload["applicant_id"]  # identity is ours, not the model's
    return parsed, result.provider


def generate_proposal(
    candidate: CandidateProfile,
    *,
    field_of_study: str = "",
    research_interests: str = "",
    career_goal: str = "",
    target_program: str = "",
    funding_body: str = "",
    supervisor: str = "",
    applicant_id: str = "",
    degree_level: str = "MSc",
    language: str = "en",
    client: LLMClient | None = None,
    chain: list | None = None,
    run_id: str = "0",
) -> ProposalArtifact:
    """Schema-valid research proposal for ``candidate`` — deterministic first."""
    payload = _deterministic(
        candidate,
        field_of_study=field_of_study,
        research_interests=research_interests,
        career_goal=career_goal,
        target_program=target_program,
        funding_body=funding_body,
        applicant_id=applicant_id,
        degree_level=degree_level,
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
                field_of_study=field_of_study,
                research_interests=research_interests,
                career_goal=career_goal,
                target_program=target_program,
                funding_body=funding_body,
                applicant_id=applicant_id,
                supervisor=supervisor,
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

    envelope: dict[str, object] = {}
    if client is not None:
        key = hashlib.sha256(
            f"proposal|{applicant_id}|{target_program}|{field_of_study}".encode()
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
            task_id="3.3",
            run_id=run_id,
            prompt_version="v1",
            idempotency_key=key,
        )
    return ProposalArtifact(
        payload=payload,
        provider=provider,
        polished=polished,
        fallback=fallback,
        envelope=envelope,
    )
