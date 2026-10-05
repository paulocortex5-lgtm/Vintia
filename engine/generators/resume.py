"""ATS resume generator (task 2.7).

Two layers, in order:

1. **Deterministic tailoring** — a :class:`CandidateProfile` and a
   :class:`JobListing` become an ATS-parseable resume: plain markdown, no
   tables/graphics/HTML, job-matched skills first, a tailored summary.
   This is the ship layer: no provider, no key, no network required.
2. **Optional LLM polish** — when an ``LLMClient`` plus a non-empty
   provider chain are supplied, a model rewrites the resume. The
   untrusted job description is *injection-guarded* and *PII-redacted*
   before it enters the prompt, and any provider failure falls back to
   the deterministic layer rather than failing the generation.

Guardrails (tasks 2.5/2.6) run unconditionally:
  * ``injection.guard`` on the listing — a job posting is untrusted
    third-party text; embedded instruction overrides abort the run;
  * ``fraud.block`` on the listing — a resume is never generated for a
    block-worthy visa-mill posting.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from ..errors import AllProvidersExhausted
from ..llm import LLMClient, LLMResult, build_envelope
from ..llm.client import is_dry_run
from ..security import fraud, injection
from ..security.redact import redact as redact_pii
from ..sources.portals.base import JobListing

__all__ = [
    "CandidateProfile",
    "Education",
    "Experience",
    "ResumeArtifact",
    "generate_resume",
]

SKILL_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "you",
        "our",
        "with",
        "have",
        "that",
        "this",
        "will",
        "are",
        "your",
        "from",
        "not",
        "but",
        "new",
        "how",
        "all",
        "any",
        "can",
        "its",
        "job",
        "role",
        "team",
        "work",
        "years",
        "year",
        "strong",
        "great",
        "best",
        "top",
        "plus",
        "etc",
        "per",
        "via",
    }
)


@dataclass(frozen=True)
class Education:
    degree: str
    school: str
    year: str = ""


@dataclass(frozen=True)
class Experience:
    role: str
    org: str
    start: str = ""
    end: str = ""
    summary: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateProfile:
    name: str
    title: str
    email: str = ""
    phone: str = ""
    location: str = ""
    summary: str = ""
    skills: tuple[str, ...] = ()
    experience: tuple[Experience, ...] = ()
    education: tuple[Education, ...] = ()
    languages: tuple[str, ...] = ()


@dataclass
class ResumeArtifact:
    markdown: str
    payload: dict[str, object]
    matched_keywords: tuple[str, ...]
    missed_keywords: tuple[str, ...]
    provider: str = "deterministic"
    polished: bool = False
    fallback: bool = False
    envelope: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "markdown": self.markdown,
            "payload": self.payload,
            "matched_keywords": list(self.matched_keywords),
            "missed_keywords": list(self.missed_keywords),
            "provider": self.provider,
            "polished": self.polished,
            "fallback": self.fallback,
            "envelope": self.envelope,
        }


def _listing_text(listing: JobListing) -> str:
    return " ".join(
        (listing.title, listing.description or "", listing.company, listing.location)
    ).strip()


def _job_keywords(listing: JobListing) -> tuple[str, ...]:
    """Word tokens from the posting, de-duplicated and de-noised."""
    words: list[str] = []
    for raw in _listing_text(listing).lower().split():
        token = "".join(ch for ch in raw if ch.isalnum() or ch in ("-", "+", "#"))
        if len(token) >= 3 and token not in SKILL_STOPWORDS and not token.isdigit():
            words.append(token)
    seen: set[str] = set()
    unique: list[str] = []
    for token in words:
        if token not in seen:
            seen.add(token)
            unique.append(token)
    return tuple(unique)


def _match_skills(
    skills: tuple[str, ...], keywords: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split skills into (matched, unmatched) against the posting keywords."""
    matched: list[str] = []
    unmatched: list[str] = []
    for skill in skills:
        lowered = skill.lower()
        if any(lowered == kw or lowered in kw or kw in lowered for kw in keywords):
            matched.append(skill)
        else:
            unmatched.append(skill)
    return tuple(matched), tuple(unmatched)


def _skill_line(matched: tuple[str, ...], unmatched: tuple[str, ...]) -> str:
    ordered = matched + unmatched
    if not ordered:
        return "N/A"
    return ", ".join(ordered)


def _build_markdown(
    candidate: CandidateProfile,
    listing: JobListing,
    matched: tuple[str, ...],
    unmatched: tuple[str, ...],
) -> str:
    """Deterministic, ATS-safe markdown: headings, bullets, no tables/HTML."""
    lines: list[str] = []
    lines.append(f"# {candidate.name}")
    lines.append(f"**{candidate.title}**")
    contact = "  |  ".join(
        part for part in (candidate.email, candidate.phone, candidate.location) if part
    )
    if contact:
        lines.append(contact)
    lines.append("")
    lines.append("## Summary")
    if listing.title:
        lines.append(
            f"{candidate.summary or 'Experienced professional.'} Seeking a {listing.title.lower()} role at {listing.company}."
        )
    else:
        lines.append(candidate.summary or "Experienced professional.")
    lines.append("")
    if matched:
        lines.append("## Key skills for this role")
        lines.append(_skill_line(matched, ()))
        lines.append("")
    if candidate.experience:
        lines.append("## Experience")
        for exp in candidate.experience:
            span = " — ".join(part for part in (exp.start, exp.end) if part)
            header = f"- **{exp.role}**, {exp.org}"
            if span:
                header += f" ({span})"
            lines.append(header)
            for detail in exp.summary:
                lines.append(f"  - {detail}")
        lines.append("")
    if candidate.education:
        lines.append("## Education")
        for edu in candidate.education:
            line = f"- {edu.degree}, {edu.school}"
            if edu.year:
                line += f" ({edu.year})"
            lines.append(line)
        lines.append("")
    if unmatched:
        lines.append("## Other skills")
        lines.append(_skill_line((), unmatched))
        lines.append("")
    if candidate.languages:
        lines.append("## Languages")
        lines.append(", ".join(candidate.languages))
    return "\n".join(lines)


def _payload(
    candidate: CandidateProfile,
    listing: JobListing,
    matched: tuple[str, ...],
    unmatched: tuple[str, ...],
) -> dict[str, object]:
    return {
        "name": candidate.name,
        "title": candidate.title,
        "contact": {
            "email": candidate.email,
            "phone": candidate.phone,
            "location": candidate.location,
        },
        "summary": candidate.summary,
        "target_role": listing.title,
        "target_company": listing.company,
        "matched_skills": list(matched),
        "other_skills": list(unmatched),
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
        "languages": list(candidate.languages),
    }


def _idempotency_key(candidate: CandidateProfile, listing: JobListing) -> str:
    basis = f"{candidate.name}|{listing.external_id}|{listing.url}".encode()
    return hashlib.sha256(basis).hexdigest()[:24]


def _polish(
    candidate: CandidateProfile,
    listing: JobListing,
    deterministic: str,
    client: LLMClient,
    chain: list,
    *,
    run_id: str,
) -> tuple[str, bool, str] | None:
    """Optional LLM polish. Returns ``(text, dry_run, provider)`` or ``None``."""
    # The job posting is untrusted: redact PII before it touches the prompt.
    redacted_blob = redact_pii(_listing_text(listing)).text
    messages = [
        {
            "role": "user",
            "content": (
                "Rewrite the candidate's resume below so it tailors better to the target role.\n"
                "Keep it ATS-parseable plain markdown (no tables, no graphics). Do not add facts "
                "that are not in the resume. Return only the markdown.\n\n"
                "TARGET ROLE (already PII-redacted):\n"
                + redacted_blob
                + "\n\nRESUME:\n"
                + deterministic
            ),
        }
    ]
    result = client.run_chain(
        chain,  # type: ignore[arg-type]
        messages,
        system="You are an expert resume writer. Output markdown only.",
        temperature=0.0,
        run_id=run_id,
    )
    return result.text, result.dry_run, result.provider


def generate_resume(
    candidate: CandidateProfile,
    listing: JobListing,
    *,
    client: LLMClient | None = None,
    chain: list | None = None,
    run_id: str = "0",
    skip_fraud: bool = False,
    skip_injection: bool = False,
) -> ResumeArtifact:
    """Generate an ATS-safe resume for ``candidate`` targeting ``listing``.

    Runs the guardrails (injection + fraud) unless explicitly skipped,
    builds the deterministic resume, then optionally polishes it with the
    LLM when a ``client`` and a non-empty ``chain`` are supplied. Provider
    failure degrades to the deterministic layer (``fallback=True``).
    """
    if not skip_injection:
        injection.guard(listing.description or listing.title, mode="untrusted")
    if not skip_fraud:
        fraud.block(listing)

    keywords = _job_keywords(listing)
    matched, unmatched = _match_skills(candidate.skills, keywords)
    markdown = _build_markdown(candidate, listing, matched, unmatched)
    payload = _payload(candidate, listing, matched, unmatched)
    provider = "deterministic"
    polished = False
    fallback = False

    if client is not None and chain:
        try:
            outcome = _polish(
                candidate,
                listing,
                markdown,
                client,
                chain,
                run_id=run_id,
            )
        except AllProvidersExhausted:
            outcome = None
        if outcome is not None:
            text, dry_run, used_provider = outcome
            if not dry_run:
                markdown = text
                provider = used_provider
                polished = True
        else:
            fallback = True

    envelope: dict[str, object] = {}
    if client is not None:
        result = LLMResult(
            text=markdown,
            provider=provider,
            model="",
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            dry_run=is_dry_run(None),
        )
        envelope = build_envelope(
            payload,
            result,
            task_id="2.7",
            run_id=run_id,
            prompt_version="v1",
            idempotency_key=_idempotency_key(candidate, listing),
        )

    return ResumeArtifact(
        markdown=markdown,
        payload=payload,
        matched_keywords=matched,
        missed_keywords=tuple(kw for kw in keywords if kw not in matched),
        provider=provider,
        polished=polished,
        fallback=fallback,
        envelope=envelope,
    )
