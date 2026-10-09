"""ATS scoring engine (task 9.2) — the twelve-point rubric.

Every category scores 0-100 and carries a fixed weight; the overall score
is the weighted mean rounded to one decimal. Missing data lowers the
*relevant* category and emits a suggestion — it never fabricates points
and never invents resume facts.

Scoring policy (documented so no number is a mystery):

* A category the posting **does not demand** scores 100: if the posting
  asks for no certification, no specific location and no language, there
  is no gap for the applicant to close. Demands are detected with the
  explicit keyword rules below — never guessed.
* Every category scoring below 100 ships at least one suggestion;
  ``keyword_match`` suggestions come from the gap report (one per missing
  keyword, placement-honest).
* Dated facts only: experience spans come from parsed dates
  (``ParsedResume.years_experience``); undated entries contribute nothing
  rather than an estimate, and the report says so.
* The resume itself is parsed in 9.1 (:mod:`engine.ats.parser`); this
  module only scores what was honestly parsed. A category below 100 is a
  *gap*, not a judgement of the applicant.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date

from .keywords import gap_report, job_keywords, keyword_coverage, match_keywords, resume_keywords
from .parser import ParsedResume, _span_month

__all__ = ["CATEGORY_WEIGHTS", "ScoreReport", "score_resume"]

#: the twelve scoring categories and their fixed contribution to /100.
CATEGORY_WEIGHTS: dict[str, float] = {
    "formatting": 5.0,
    "contact_info": 10.0,
    "keyword_match": 20.0,
    "job_title_match": 10.0,
    "years_experience": 10.0,
    "skills_match": 10.0,
    "education_match": 10.0,
    "certifications_match": 5.0,
    "language_match": 5.0,
    "location_match": 5.0,
    "employment_gaps": 5.0,
    "overall_impact": 5.0,
}

# ── Demand detection (explicit rules, never guesses) ──────────────────────

_YEARS_REQ_RE = re.compile(r"(\d+)\s*\+?\s*(?:-\s*\d+)?\s*(?:years?|yrs?)\b", re.IGNORECASE)
_CERT_REQ_RE = re.compile(
    r"certificat\w*|certified|clearance|licen[cs]e|\bcissp\b|\bpmp\b", re.IGNORECASE
)
_LANG_REQ_RE = re.compile(
    r"\blanguages?\b|\bfluent\b|\benglish\b|\bgerman\b|\bfrench\b|\bspanish\b"
    r"|\bportuguese\b|\barabic\b|\bmandarin\b|\bdutch\b|\bitalian\b",
    re.IGNORECASE,
)
#: highest level wins — ordered doctorate → diploma.
_LEVEL_PATTERNS: tuple[tuple[re.Pattern[str], int, str], ...] = (
    (re.compile(r"ph\.?\s?d|doctorate|dphil", re.IGNORECASE), 4, "doctorate"),
    (re.compile(r"master|mba|m\.?\s?sc|m\.?\s?a\b|magister|\bmsc\b", re.IGNORECASE), 3, "master's"),
    (
        re.compile(r"bachelor|b\.?\s?sc|b\.?\s?a\b|undergraduate|\bdegree\b", re.IGNORECASE),
        2,
        "bachelor's",
    ),
    (re.compile(r"diploma|hnd|associate|btec", re.IGNORECASE), 1, "diploma"),
)
_LEVEL_LABELS = {level: label for _pattern, level, label in _LEVEL_PATTERNS}

_QUANTIFIED_RE = re.compile(
    r"\d+(?:\.\d+)?\s*%|\$\s?\d+(?:\.\d+)?|\b\d{1,3}(?:,\d{3})+\b", re.IGNORECASE
)
_IMPACT_VERBS_RE = re.compile(
    r"\b(shipped|led|built|reduced|increased|designed|implemented|launched|migrated"
    r"|automated|improved|delivered|owned|managed|created|developed|grew|cut|scaled"
    r"|drove|mentored|negotiated|resolved|streamlined)\b",
    re.IGNORECASE,
)
_PRESENT_TOKENS = frozenset({"present", "current", "ongoing", "now"})


def _level(text: str) -> int:
    """Highest qualification level ``text`` mentions (0 = none detected)."""
    for pattern, level, _label in _LEVEL_PATTERNS:
        if pattern.search(text):
            return level
    return 0


def _priority(name: str) -> str:
    weight = CATEGORY_WEIGHTS[name]
    if weight >= 10:
        return "high"
    return "medium" if weight >= 5 else "low"


def _suggestion(name: str, text: str) -> dict[str, str]:
    return {"category": name, "priority": _priority(name), "suggestion": text}


# ── Category scorers (each returns (score, honest suggestion or None)) ────


def _formatting(resume: ParsedResume) -> tuple[float, str | None]:
    body = resume.raw_text or " ".join(str(v) for v in resume.sections.values())
    score = 40.0 if len(body) >= 400 else round((len(body) / 400.0) * 40.0, 1)
    filled = sum(1 for v in resume.sections.values() if str(v).strip())
    score += 30.0 if filled >= 3 else 15.0 if filled >= 2 else 0.0
    if resume.skills and resume.experience:
        score += 30.0
    elif resume.skills or resume.experience:
        score += 15.0
    score = round(min(100.0, score), 1)
    if score < 100.0:
        return score, (
            "The resume is thin or lacks recognised sections (Summary, Skills, "
            "Experience, Education); expand it with your real history so ATS "
            "parsers can split it reliably."
        )
    return score, None


def _contact_info(resume: ParsedResume) -> tuple[float, str | None]:
    score = 0.0
    missing: list[str] = []
    if resume.email:
        score += 40.0
    else:
        missing.append("email address")
    if resume.phone:
        score += 30.0
    else:
        missing.append("phone number")
    if resume.location:
        score += 15.0
    else:
        missing.append("location line (Location: City)")
    if resume.name:
        score += 15.0
    else:
        missing.append("full name")
    if missing:
        return score, (
            "Add your "
            + ", ".join(missing)
            + " — recruiters and ATS filters route on contact details; never "
            "invent any you do not use."
        )
    return score, None


def _job_title_match(
    resume: ParsedResume, job_title: str, present: list[str]
) -> tuple[float, str | None]:
    wanted = [k for k in job_keywords(job_title) if " " not in k]
    if not wanted:
        return 100.0, None
    matched, _missing, _how = match_keywords(wanted, present)
    score = round(len(matched) / len(wanted) * 100.0, 1)
    if score < 100.0:
        return score, (
            f"The posting is titled '{job_title.strip()}' and your headline/"
            "summary does not use that wording; mirror the exact title in your "
            "headline when it honestly describes your role."
        )
    return score, None


def _years_experience(resume: ParsedResume, job_description: str) -> tuple[float, str | None]:
    years = resume.years_experience
    req = _YEARS_REQ_RE.search(job_description)
    if req is not None:
        need = float(req.group(1))
        if need > 0:
            score = round(min(100.0, (years / need) * 100.0), 1)
            if score < 100.0:
                return score, (
                    f"The posting asks for {int(need)}+ years; your dated entries "
                    f"evidence {years:g} years. Add dates (YYYY or Mon YYYY) to "
                    "undated roles or state your true total — never inflate it."
                )
    if years >= 3:
        return 100.0, None
    if years >= 1:
        return 90.0, None
    if years > 0:
        return 75.0, None
    return 40.0, (
        "No dated experience entries were found, so tenure cannot be computed. "
        "Add start/end dates to your roles (education and projects count too)."
    )


def _skills_match(resume: ParsedResume, required: list[str]) -> tuple[float, str | None]:
    if not required:
        return 100.0, None
    if not resume.skills:
        return 0.0, (
            "The resume has no Skills section; add one listing skills you "
            "genuinely hold, mirroring the posting's exact wording where true."
        )
    matched, _missing, _how = match_keywords(required, resume.skills)
    score = round(len(matched) / len(required) * 100.0, 1)
    if score < 100.0:
        return score, (
            f"Only {len(matched)} of {len(required)} posting keywords appear in "
            "your Skills section; add the ones you genuinely hold (the gap "
            "report lists them individually)."
        )
    return score, None


def _education_match(resume: ParsedResume, job_text: str) -> tuple[float, str | None]:
    demand = _level(job_text)
    if demand == 0:
        return 100.0, None
    label = _LEVEL_LABELS[demand]
    have = max((_level(str(e.get("degree", ""))) for e in resume.education), default=0)
    if have == 0:
        return 0.0, (
            f"The posting asks for a {label} qualification and no education "
            "entry was found — add the qualification you actually hold; never "
            "claim one you do not."
        )
    if have >= demand:
        return 100.0, None
    return 50.0, (
        f"Your highest listed qualification reads below the {label} the posting "
        "asks for; if your credential is equivalent, say so with its official "
        "name and awarding body."
    )


def _certifications_match(resume: ParsedResume, job_text: str) -> tuple[float, str | None]:
    if _CERT_REQ_RE.search(job_text) is None:
        return 100.0, None
    if resume.certifications:
        return 100.0, None
    return 0.0, (
        "The posting mentions a certification/clearance and none is listed; "
        "add certifications you actually hold (name, issuer, year)."
    )


def _language_match(resume: ParsedResume, job_text: str) -> tuple[float, str | None]:
    if _LANG_REQ_RE.search(job_text) is None:
        return 100.0, None
    if resume.languages:
        return 100.0, None
    return 0.0, (
        "The posting references a language requirement and none is listed; "
        "add the languages you speak with your honest proficiency level."
    )


def _location_match(
    resume: ParsedResume, job_location: str, job_description: str
) -> tuple[float, str | None]:
    blob = f"{job_location} {job_description}".casefold()
    if "remote" in blob:
        return 100.0, None
    if not job_location.strip() or not resume.location.strip():
        return 100.0, None  # nothing to compare — no demand, no gap

    def _tokens(value: str) -> list[str]:
        return [w for w in re.findall(r"[a-z]+", value.casefold()) if len(w) > 2]

    have = _tokens(resume.location)
    want = _tokens(job_location)
    if not have or not want:
        return 100.0, None
    if want[0] in have or have[0] in want:
        return 100.0, None
    if set(have) & set(want):
        return 70.0, (
            f"Your location '{resume.location.strip()}' is in the same region "
            f"as the posting ('{job_location.strip()}') but not the same city; "
            "state your actual city and willingness to relocate, if true."
        )
    return 0.0, (
        f"Your location '{resume.location.strip()}' does not match the posting "
        f"('{job_location.strip()}'); correct it if you are based there or "
        "willing to relocate — mismatches fail automated screening."
    )


def _employment_gaps(resume: ParsedResume) -> tuple[float, str | None]:
    spans: list[tuple[date, date]] = []
    for entry in resume.experience:
        start = _span_month(str(entry.get("start", "")))
        end_text = str(entry.get("end", ""))
        end = _span_month("present" if end_text.strip().casefold() in _PRESENT_TOKENS else end_text)
        if start is None or end is None:
            continue
        if end < start:
            start, end = end, start
        spans.append((start, end))
    if not spans:
        return 100.0, None  # nothing dated to gap-check; years_experience reports this
    spans.sort()
    score = 100.0
    prev_end = spans[0][1]
    had_gap = False
    for start, end in spans[1:]:
        if start > prev_end:
            months = (start.year - prev_end.year) * 12 + (start.month - prev_end.month)
            if months > 6:
                score -= 35.0
                had_gap = True
        prev_end = max(prev_end, end)
    score = max(0.0, round(score, 1))
    if had_gap and score < 100.0:
        return score, (
            "A gap of more than six months appears between dated entries; "
            "fill it with your real contract/freelance/study spans for the "
            "period — never invent one."
        )
    return score, None


def _overall_impact(resume: ParsedResume) -> tuple[float, str | None]:
    parts: list[str] = [resume.summary, resume.raw_text]
    for entry in resume.experience:
        parts.extend(str(s) for s in entry.get("summary", []) or [])
    body = " ".join(p for p in parts if p)
    score = 0.0
    if resume.summary.strip():
        score += 40.0
    if _QUANTIFIED_RE.search(body):
        score += 30.0
    if _IMPACT_VERBS_RE.search(body):
        score += 30.0
    if score >= 100.0:
        return 100.0, None
    return score, (
        "Add a professional summary and quantify outcomes (%, £/$ figures, "
        "counts) in your experience bullets using your real results — vague "
        "bullets score poorly against ATS impact filters."
    )


class ScoreReport:
    """One scored resume: categories, keywords, gaps, suggestions."""

    def __init__(
        self,
        resume: ParsedResume,
        job_title: str,
        required: list[str],
        matched: list[str],
        missing: list[str],
        category_scores: dict[str, float],
        suggestions: list[dict[str, str]],
    ) -> None:
        self.resume = resume
        self.job_title = job_title
        self.required = required
        self.matched = matched
        self.missing = missing
        self.category_scores = category_scores
        self.suggestions = suggestions
        self.coverage = keyword_coverage(required, matched)
        self.overall = round(
            sum(score * CATEGORY_WEIGHTS[name] for name, score in category_scores.items()) / 100.0,
            1,
        )

    def payload(self, *, resume_id: str = "", job_id: str = "") -> dict[str, object]:
        """The schema-valid report body for ``ats_score.schema.json``."""
        return {
            "resume_id": resume_id,
            "job_id": job_id,
            "overall_score": self.overall,
            "category_scores": dict(self.category_scores),
            "keyword_coverage": self.coverage,
            "matched_keywords": list(self.matched),
            "missing_keywords": list(self.missing),
            "improvement_suggestions": [dict(s) for s in self.suggestions],
            "parser_metadata": self.resume.metadata,
        }


# name → scorer; job_title/location variants are wired in score_resume().
_SCORERS: dict[str, Callable[..., tuple[float, str | None]]] = {
    "formatting": lambda resume, job_text, ctx: _formatting(resume),
    "contact_info": lambda resume, job_text, ctx: _contact_info(resume),
    "years_experience": lambda resume, job_text, ctx: _years_experience(
        resume, str(ctx["job_description"])
    ),
    "skills_match": lambda resume, job_text, ctx: _skills_match(resume, list(ctx["required"])),
    "education_match": lambda resume, job_text, ctx: _education_match(resume, job_text),
    "certifications_match": lambda resume, job_text, ctx: _certifications_match(resume, job_text),
    "language_match": lambda resume, job_text, ctx: _language_match(resume, job_text),
    "employment_gaps": lambda resume, job_text, ctx: _employment_gaps(resume),
    "overall_impact": lambda resume, job_text, ctx: _overall_impact(resume),
}


def score_resume(
    resume: ParsedResume,
    *,
    job_title: str = "",
    job_description: str = "",
    job_location: str = "",
    required: list[str] | None = None,
) -> ScoreReport:
    """Score ``resume`` against the target job with the twelve-point rubric.

    Deterministic and offline: same inputs → same report. ``required``
    defaults to the posting's keyword set (9.3); pass it explicitly to
    score against a curated list instead.
    """
    if required is None:
        required = job_keywords(job_description, title=job_title)
    present = resume_keywords(resume)
    matched, missing, how = match_keywords(required, present)
    job_text = f"{job_title}\n{job_description}"
    ctx: dict[str, object] = {"job_description": job_description, "required": required}

    scores: dict[str, float] = {}
    suggestions: list[dict[str, str]] = []

    for name in CATEGORY_WEIGHTS:
        if name == "keyword_match":
            scores[name] = round(keyword_coverage(required, matched) * 100.0, 1)
        elif name == "job_title_match":
            scores[name], hint = _job_title_match(resume, job_title, present)
            if hint is not None:
                suggestions.append(_suggestion(name, hint))
        elif name == "location_match":
            scores[name], hint = _location_match(resume, job_location, job_description)
            if hint is not None:
                suggestions.append(_suggestion(name, hint))
        else:
            scores[name], hint = _SCORERS[name](resume, job_text, ctx)
            if hint is not None:
                suggestions.append(_suggestion(name, hint))

    # keyword gaps: one placement-honest suggestion per missing keyword
    suggestions.extend(gap_report(required, matched, missing, how))
    if set(scores) != set(CATEGORY_WEIGHTS):  # pragma: no cover — defensive
        raise AssertionError("every category must be scored")
    return ScoreReport(
        resume=resume,
        job_title=job_title,
        required=list(required),
        matched=matched,
        missing=missing,
        category_scores=scores,
        suggestions=suggestions,
    )
