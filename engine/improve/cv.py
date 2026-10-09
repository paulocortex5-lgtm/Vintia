"""CV improvement engine (task 10.2) — deterministic-first targeted rewriting.

Turns a parsed resume (9.1) into an *improved CV* plus a reviewable list of
edits, matching ``cv_improvement.schema.json`` on every path.

The deterministic layer (no provider, no key, no network) only makes edits
that preserve every fact:

* **structure** — rebuild the document in canonical section order (and
  render a structured JSON profile into a real CV);
* **content** — flag missing sections with the *honest placeholder* line
  the 2.7 resume generator already ships — never an invented summary;
* **keyword_optimization** — mirror a keyword that already appears in your
  experience/education into the Skills section (no new claim is created);
  with no job description there is nothing to mirror;
* **action_verbs** — swap weak bullet openers using the table the shipped
  prompt itself sanctions (``worked on`` → ``engineered`` …); the edit is
  listed for review, never silently applied to your facts;
* **clarity** — drop filler phrases (``in order to`` → ``to``) and
  whitespace noise.

Numbers, grammar rewrites and anything that would require *inventing* text
are left to the optional LLM polish, which is schema-validated, capped at
30 improvements, and never allowed to change ``original_cv_id``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ..ats.keywords import job_keywords, match_keywords
from ..ats.parser import ParsedResume
from ..errors import AllProvidersExhausted, SchemaValidationError, VantiaError
from ..json_utils import load_json, safe_parse, validate
from ..llm import LLMClient, LLMResult, build_envelope
from ..llm.client import is_dry_run

__all__ = ["ImproveArtifact", "improve_cv"]

_MAX_IMPROVEMENTS = 30  # prompt constraint: max 30, ranked by priority

#: category → (impact, priority 1-10) used for deterministic edits.
_CATEGORY_META: dict[str, tuple[str, int]] = {
    "metrics": ("high", 10),
    "keyword_optimization": ("high", 9),
    "content": ("high", 8),
    "structure": ("medium", 7),
    "action_verbs": ("medium", 6),
    "formatting": ("medium", 5),
    "clarity": ("low", 4),
    "grammar": ("low", 3),
}

#: weak bullet openers the shipped ``v1_cv_improve.md`` sanctions replacing.
_VERB_TABLE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bwas responsible for\b", re.IGNORECASE), "owned"),
    (re.compile(r"\bworked on\b", re.IGNORECASE), "engineered"),
    (re.compile(r"\bhelped with\b", re.IGNORECASE), "delivered"),
)

#: filler → tighter wording (meaning preserved).
_FILLER_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bin order to\b", re.IGNORECASE), "to"),
    (re.compile(r"\bdue to the fact that\b", re.IGNORECASE), "because"),
    (re.compile(r"\ba number of\b", re.IGNORECASE), "several"),
    (re.compile(r"\s*,?\s*\betc\.?\s*$", re.IGNORECASE), ""),
)

#: document order an ATS expects.
_CORE_SECTIONS: tuple[str, ...] = ("summary", "skills", "experience", "education")
_SECTION_HEADINGS: dict[str, str] = {
    "summary": "Summary",
    "skills": "Skills",
    "experience": "Experience",
    "education": "Education",
    "languages": "Languages",
    "certifications": "Certifications",
}

_SUMMARY_PLACEHOLDER = (
    "(The original had no professional summary — add 2-3 lines about your "
    "real background and target role.)"
)
_SKILLS_PLACEHOLDER = "(The original had no skills section - list the skills you genuinely hold.)"


def _schema() -> dict[str, Any]:
    path = "engine/schemas/cv_improvement.schema.json"
    schema = load_json(path)
    if schema is None:  # pragma: no cover — packaged file must exist
        raise VantiaError("cv_improvement.schema.json missing", code="schema_missing")
    return schema


def _prompt() -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", "v1_cv_improve.md")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _words(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def _entry(
    category: str,
    *,
    section: str,
    original: str,
    improved: str,
    reason: str,
) -> dict[str, Any]:
    impact, priority = _CATEGORY_META[category]
    return {
        "category": category,
        "section": section,
        "original_text": original,
        "improved_text": improved,
        "reason": reason,
        "impact": impact,
        "priority": priority,
    }


@dataclass
class ImproveArtifact:
    """One improved CV: payload + provenance (mirrors ``SopArtifact``)."""

    payload: dict[str, Any]
    provider: str = "deterministic"
    polished: bool = False
    fallback: bool = False
    envelope: dict[str, Any] = field(default_factory=dict)

    @property
    def improved_cv(self) -> str:
        return str(self.payload.get("improved_cv", ""))

    @property
    def improvements(self) -> list[dict[str, Any]]:
        return list(self.payload.get("improvements", []))

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload": self.payload,
            "provider": self.provider,
            "polished": self.polished,
            "fallback": self.fallback,
            "envelope": self.envelope,
        }


# ── Deterministic transforms (facts are never touched) ────────────────────


def _transform(text: str) -> tuple[str, list[tuple[str, str, str]]]:
    """Apply verb + filler rules; return ``(new_text, [(orig, new, category)])``."""
    out = text
    changes: list[tuple[str, str, str]] = []
    for pattern, replacement in _VERB_TABLE:

        def _swap(match: re.Match[str], *, repl: str = replacement) -> str:
            return repl.capitalize() if match.group(0)[:1].isupper() else repl

        new = pattern.sub(_swap, out)
        if new != out:
            changes.append((out, new, "action_verbs"))
            out = new
    for pattern, replacement in _FILLER_RULES:
        new = pattern.sub(replacement, out)
        if new != out:
            changes.append((out, new, "clarity"))
            out = new
    return out, changes


def _render(
    resume: ParsedResume,
    *,
    skills: list[str],
    experience: list[dict[str, Any]],
    summary: str,
) -> str:
    """Canonical, ATS-parseable rendering of the (already improved) facts."""
    lines: list[str] = []
    if resume.name:
        lines.append(resume.name)
    if resume.title:
        lines.append(resume.title)
    contact = []
    if resume.location:
        contact.append(f"Location: {resume.location}")
    if resume.email:
        contact.append(resume.email)
    if resume.phone:
        contact.append(resume.phone)
    if resume.website:
        contact.append(resume.website)
    if contact:
        lines.append(" | ".join(contact))

    def add(heading: str, body: list[str]) -> None:
        if body:
            lines.extend(["", f"## {heading}", *body])

    add("Summary", [summary] if summary.strip() else [])
    add("Skills", [", ".join(skills)] if skills else [])

    exp_body: list[str] = []
    for entry in experience:
        role = str(entry.get("role", "")).strip()
        org = str(entry.get("org", "")).strip()
        if not role and not org:
            continue
        start = str(entry.get("start", "")).strip()
        end = str(entry.get("end", "")).strip()
        if start and end:
            span = f" ({start} – {end})"
        elif start:
            span = f" ({start})"
        elif end:
            span = f" ({end})"
        else:
            span = ""
        header = f"{role}, {org}{span}" if role and org else f"{role or org}{span}"
        exp_body.append(header)
        exp_body.extend(f"- {b}" for b in entry.get("summary", []) or [])
    add("Experience", exp_body)

    edu_body = []
    for item in resume.education:
        degree = str(item.get("degree", "")).strip()
        if not degree:
            continue
        school = str(item.get("school", "")).strip()
        year = str(item.get("year", "")).strip()
        line = degree + (f", {school}" if school else "") + (f" ({year})" if year else "")
        edu_body.append(line)
    add("Education", edu_body)
    if resume.languages:
        add("Languages", [", ".join(resume.languages)])
    if resume.certifications:
        add("Certifications", [", ".join(resume.certifications)])
    return "\n".join(lines).strip()


_VERB_REASON = (
    "Weak opener replaced per the shipped v1_cv_improve guidance; review that "
    "the stronger verb still describes your work before sending."
)
_FILLER_REASON = "Filler phrasing tightened; the meaning is unchanged."


def _deterministic(
    resume: ParsedResume,
    *,
    original_cv_id: str,
    job_description: str,
    job_title: str,
) -> dict[str, Any]:
    """Fact-preserving improvements + the rebuilt CV (validated on return)."""
    improvements: list[dict[str, Any]] = []

    # 1. transform bullet text and the summary (roles/orgs/dates untouched)
    experience: list[dict[str, Any]] = []
    for entry in resume.experience:
        new_entry = dict(entry)
        bullets: list[str] = []
        for bullet in [str(b) for b in entry.get("summary", []) or []]:
            fixed, changes = _transform(bullet)
            for original, improved, category in changes:
                improvements.append(
                    _entry(
                        category,
                        section="Professional Experience",
                        original=original,
                        improved=improved,
                        reason=_VERB_REASON if category == "action_verbs" else _FILLER_REASON,
                    )
                )
            bullets.append(fixed)
        new_entry["summary"] = bullets
        experience.append(new_entry)

    summary = resume.summary
    if summary.strip():
        fixed_summary, changes = _transform(summary)
        for original, improved, category in changes:
            improvements.append(
                _entry(
                    category,
                    section="Summary",
                    original=original,
                    improved=improved,
                    reason=_VERB_REASON if category == "action_verbs" else _FILLER_REASON,
                )
            )
        summary = fixed_summary

    # 2. mirror keywords that exist elsewhere in the resume into Skills
    skills = list(resume.skills)
    if job_description.strip():
        required = job_keywords(job_description, title=job_title or resume.title)
        _matched, missing, _how = match_keywords(required, skills)
        # evidence = concrete claims only (bullets + education); the summary
        # and headline are already visible in the document, and job-title
        # words are role words, not skills.
        evidence = " ".join(
            [b for e in experience for b in e.get("summary", []) or []]
            + [str(e.get("degree", "")) for e in resume.education]
            + [str(e.get("school", "")) for e in resume.education]
        )
        have = {s.casefold() for s in skills}
        mirrors = 0
        for keyword in missing:
            if mirrors >= 10:
                break
            found = re.search(
                rf"(?<![\w.+#-]){re.escape(keyword)}(?![\w.+#-])",
                evidence,
                re.IGNORECASE,
            )
            if found is None:
                continue
            surface = found.group(0).strip()
            if not surface or surface.casefold() in have:
                continue
            before = ", ".join(skills)
            skills.append(surface)
            have.add(surface.casefold())
            mirrors += 1
            improvements.append(
                _entry(
                    "keyword_optimization",
                    section="Skills",
                    original=before or "(empty)",
                    improved=", ".join(skills),
                    reason=(
                        f"'{surface}' already appears in your experience/education but "
                        "was missing from Skills — mirrored, no new claim."
                    ),
                )
            )

    # 3. honest placeholders for missing sections
    if not summary.strip():
        improvements.append(
            _entry(
                "content",
                section="Summary",
                original="(missing)",
                improved=_SUMMARY_PLACEHOLDER,
                reason=(
                    "ATS filters look for a professional summary; the placeholder "
                    "marks where your real one goes — write it yourself."
                ),
            )
        )
        summary = _SUMMARY_PLACEHOLDER
    if not skills:
        improvements.append(
            _entry(
                "content",
                section="Skills",
                original="(missing)",
                improved=_SKILLS_PLACEHOLDER,
                reason=(
                    "No Skills section found; the placeholder marks where your "
                    "genuine skill list goes."
                ),
            )
        )
        skills = [_SKILLS_PLACEHOLDER]

    # 4. structure: canonical order / JSON profile rendered / core section rebuild
    present_core = [
        key
        for key in resume.sections
        if key in _CORE_SECTIONS and str(resume.sections[key]).strip()
    ]
    canonical_present = [key for key in _CORE_SECTIONS if key in present_core]
    reasons: list[str] = []
    if resume.source_format == "json":
        reasons.append("structured profile rendered into an ATS-parseable CV")
    if present_core != canonical_present:
        reasons.append(
            "sections reordered to the ATS convention "
            f"({' → '.join(_SECTION_HEADINGS[k] for k in canonical_present)})"
        )
    if "experience" not in present_core and experience:
        reasons.append("Experience section rebuilt from the dated entries")
    if "education" not in present_core and resume.education:
        reasons.append("Education section rebuilt from the education entries")
    if reasons:
        rendered_heads = [_SECTION_HEADINGS["summary"], _SECTION_HEADINGS["skills"]]
        if experience:
            rendered_heads.append(_SECTION_HEADINGS["experience"])
        if resume.education:
            rendered_heads.append(_SECTION_HEADINGS["education"])
        improvements.append(
            _entry(
                "structure",
                section="Document",
                original=", ".join(_SECTION_HEADINGS[k] for k in present_core)
                or "(no sections found)",
                improved=", ".join(rendered_heads),
                reason="; ".join(reasons) + ".",
            )
        )

    # 5. formatting: whitespace noise an ATS parser may misread
    noisy = next(
        (line for line in resume.raw_text.splitlines() if re.search(r"\t|[ \t]{2,}", line)),
        "",
    )
    if noisy:
        clean = re.sub(r"[ \t]{2,}", " ", noisy.replace("\t", " ")).strip()
        improvements.append(
            _entry(
                "formatting",
                section="Document",
                original=noisy.strip()[:200],
                improved=clean[:200],
                reason=(
                    "Tabs/double spaces confuse some ATS parsers; the rebuilt "
                    "document normalises them."
                ),
            )
        )

    improved_cv = _render(resume, skills=skills, experience=experience, summary=summary)
    improvements.sort(key=lambda item: -int(item["priority"]))
    improvements = improvements[:_MAX_IMPROVEMENTS]
    impacts = Counter(item["impact"] for item in improvements)
    categories = Counter(item["category"] for item in improvements)
    payload: dict[str, Any] = {
        "original_cv_id": original_cv_id,
        "improvements": improvements,
        "improved_cv": improved_cv,
        "summary": {
            "total_improvements": len(improvements),
            "high_impact_count": impacts.get("high", 0),
            "medium_impact_count": impacts.get("medium", 0),
            "low_impact_count": impacts.get("low", 0),
            "top_categories": [name for name, _ in categories.most_common(3)],
        },
    }
    validate(payload, _schema())
    return payload


# ── Optional LLM polish (schema-validated, identity fields stay ours) ─────


def _render_prompt(
    resume: ParsedResume,
    *,
    original_cv_id: str,
    job_description: str,
    job_title: str,
    company_name: str,
    country: str,
    language: str,
) -> str:
    """Fill the shipped v1_cv_improve.md template (DATA, not instructions)."""
    text = _prompt()
    # the model must see the whole resume (name/contact included), not just
    # the flat raw_text a JSON profile would otherwise yield
    original = _render(
        resume,
        skills=list(resume.skills),
        experience=[dict(entry) for entry in resume.experience],
        summary=resume.summary,
    ) or json.dumps(resume.to_dict(), ensure_ascii=False, indent=2)
    replacements = {
        "{{ original_resume }}": original,
        "{{ job_description }}": job_description,
        "{{ company_name }}": company_name,
        "{{ job_title }}": job_title,
        "{{ country }}": country,
        "{{ language }}": language,
        "{{ original_cv_id }}": original_cv_id,
    }
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def _polish(
    payload: dict[str, Any],
    resume: ParsedResume,
    *,
    original_cv_id: str,
    job_description: str,
    job_title: str,
    company_name: str,
    country: str,
    language: str,
    client: LLMClient,
    chain: list,
    run_id: str,
) -> tuple[dict[str, Any] | None, str]:
    """Model JSON → schema-valid payload; anything else keeps ours."""
    rendered = _render_prompt(
        resume,
        original_cv_id=original_cv_id,
        job_description=job_description,
        job_title=job_title,
        company_name=company_name,
        country=country,
        language=language,
    )
    result = client.run_chain(
        chain,
        [{"role": "user", "content": rendered}],
        system="You are a senior career coach. Output only JSON matching the schema.",
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
    # identity + honesty: ours, and the summary must recount the shipped list
    parsed["original_cv_id"] = original_cv_id
    improvements = sorted(
        parsed.get("improvements") or [], key=lambda e: -int(e.get("priority", 1))
    )[:_MAX_IMPROVEMENTS]
    parsed["improvements"] = improvements
    impacts = Counter(str(e.get("impact", "low")) for e in improvements)
    categories = Counter(str(e.get("category", "")) for e in improvements)
    parsed["summary"] = {
        "total_improvements": len(improvements),
        "high_impact_count": impacts.get("high", 0),
        "medium_impact_count": impacts.get("medium", 0),
        "low_impact_count": impacts.get("low", 0),
        "top_categories": [name for name, _ in categories.most_common(3)],
    }
    return parsed, result.provider


def improve_cv(
    resume: ParsedResume,
    *,
    original_cv_id: str = "",
    job_description: str = "",
    job_title: str = "",
    company_name: str = "",
    country: str = "",
    language: str = "en",
    client: LLMClient | None = None,
    chain: list | None = None,
    run_id: str = "0",
) -> ImproveArtifact:
    """Schema-valid improved CV for ``resume`` — deterministic ship layer first."""
    payload = _deterministic(
        resume,
        original_cv_id=original_cv_id,
        job_description=job_description,
        job_title=job_title,
    )
    provider, polished, fallback = "deterministic", False, False
    if client is not None and chain:
        try:
            polished_payload, used = _polish(
                payload,
                resume,
                original_cv_id=original_cv_id,
                job_description=job_description,
                job_title=job_title,
                company_name=company_name,
                country=country,
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
        key = hashlib.sha256(
            f"cv|{original_cv_id}|{digest}|{job_description[:60]}".encode()
        ).hexdigest()[:32]
        envelope = build_envelope(
            payload,
            LLMResult(
                text=str(payload.get("improved_cv", "")),
                provider=provider,
                model="",
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                dry_run=is_dry_run(None),
            ),
            task_id="10.2",
            run_id=run_id,
            prompt_version="v1",
            idempotency_key=key,
        )
    return ImproveArtifact(
        payload=payload,
        provider=provider,
        polished=polished,
        fallback=fallback,
        envelope=envelope,
    )
