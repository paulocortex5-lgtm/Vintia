"""Mock interview generator (task 15.7, Pro).

Ten likely interview questions with model answers grounded **only** in
the candidate's parsed CV and the posting's own text — the deterministic
ship layer builds every question from real facts, so the feature works
with zero providers online; an LLM polish (Pro chains) may rephrase but
never invent experience the CV does not contain.

Order (R16/R17/R18): tier gate → balance check (4,000) → generate →
persist → debit. Idempotent per ``(scan_id, prompt_version)``.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from typing import Any

from ..ats.keywords import job_keywords, match_keywords, resume_keywords
from ..ats.parser import ParsedResume, parse_resume
from ..credits import default_ledger, ensure_allowance
from ..credits.tiers import check_feature_access, tier_of
from ..errors import FeatureNotAvailable, InsufficientCredits, VantiaError
from ..json_utils import atomic_write_json, load_json, validate
from ..logging_config import utc_now

__all__ = ["INTERVIEW_COST", "generate_interview", "load_interview"]

LOGGER = logging.getLogger("vantia.generators.mock_interview")

#: Credit price (task 15.7 §11.4).
INTERVIEW_COST = 4000

PROMPT_VERSION = "1.0.0"
FEATURE = "mock_interview"

_store_lock = threading.RLock()


def _default_dir() -> str:
    return os.environ.get("VANTIA_FEATURES_DIR", os.path.join(".vantia", "features"))


def _store_file() -> str:
    return os.path.join(_default_dir(), "mock_interviews.json")


def _schema() -> dict[str, Any]:
    schema = load_json("engine/schemas/mock_interview.schema.json")
    if schema is None:  # pragma: no cover — packaged file must exist
        raise VantiaError("mock_interview.schema.json missing", code="schema_missing")
    return schema


def _load_all() -> dict[str, Any]:
    data = load_json(_store_file())
    if not isinstance(data, dict) or not isinstance(data.get("interviews"), dict):
        return {"version": 1, "interviews": {}}
    return data


def _save_all(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_store_file()), exist_ok=True)
    atomic_write_json(_store_file(), data)


def load_interview(scan_id: str) -> dict[str, Any] | None:
    """Cached interview payload for ``scan_id``, or None."""
    return _load_all()["interviews"].get(scan_id)


def _top_experience_line(resume: ParsedResume) -> str:
    for entry in resume.experience:
        summary = entry.get("summary")
        if isinstance(summary, list) and summary:
            return str(summary[0])[:160]
        if isinstance(summary, str) and summary.strip():
            return summary[:160]
    return "the roles listed on the CV"


def _deterministic_interview(
    resume: ParsedResume, job_description: str, company_name: str
) -> dict[str, Any]:
    """Exactly 10 questions; every answer cites a CV fact (§11.1 rules)."""
    keywords = job_keywords(job_description)
    matched = match_keywords(keywords, resume_keywords(resume))[0]
    top_skills = list(resume.skills)[:4] or matched[:4] or ["the CV's core skills"]
    experience_line = _top_experience_line(resume)
    education_line = (
        str(resume.education[0].get("degree", "")) if resume.education else "the CV's education"
    )
    company = company_name or "the company"
    questions: list[dict[str, str]] = [
        {
            "question": f"Walk me through a project where you used {top_skills[0]}.",
            "model_answer": (
                f"My CV records: {experience_line}. I would walk through that "
                f"experience, the decisions I owned, and the measurable outcome."
            ),
            "competency_tag": "technical",
        },
        {
            "question": f"How have you applied {top_skills[1 % len(top_skills)]} in production?",
            "model_answer": (
                f"Grounded in my CV: {experience_line}. I would describe the "
                f"concrete usage, trade-offs and results, with no invented numbers."
            ),
            "competency_tag": "technical",
        },
        {
            "question": f"What makes you a strong fit for {company} specifically?",
            "model_answer": (
                f"My CV shows {education_line} and hands-on experience as "
                f"{resume.title or 'a professional'}. I would connect those "
                f"facts to the posting's stated requirements."
            ),
            "competency_tag": "culture_fit",
        },
        {
            "question": "Describe a time a project went wrong. What did you do?",
            "model_answer": (
                f"I would answer from my real track record — starting from "
                f"{experience_line} — describing detection, action and the "
                f"lesson institutionalised afterwards."
            ),
            "competency_tag": "problem_solving",
        },
        {
            "question": "How do you prioritise when everything is urgent?",
            "model_answer": (
                f"Using examples from my CV ({experience_line}), I would explain "
                f"how I sequence work by impact and risk."
            ),
            "competency_tag": "problem_solving",
        },
        {
            "question": "Tell me about a time you influenced a decision without authority.",
            "model_answer": (
                f"I would ground this in a real collaboration from my roles "
                f"(e.g. {experience_line}) and the outcome it produced."
            ),
            "competency_tag": "leadership",
        },
        {
            "question": "How do you handle disagreement with a teammate's technical choice?",
            "model_answer": (
                "I would describe my actual process: data first, options on the "
                "table, decision recorded — citing a real instance from my CV."
            ),
            "competency_tag": "behavioural",
        },
        {
            "question": "What is the biggest lesson from your most recent role?",
            "model_answer": (
                f"My most recent role on the CV is: {experience_line}. I would "
                f"distil the single biggest lesson and how it changed my work."
            ),
            "competency_tag": "behavioural",
        },
        {
            "question": "Where do you want to be in three years?",
            "model_answer": (
                f"Anchored on my actual trajectory in the CV ({resume.title or 'my field'}), "
                f"I would describe growth that serves {company}'s stated goals."
            ),
            "competency_tag": "culture_fit",
        },
        {
            "question": f"Do you have questions for us about {company}?",
            "model_answer": (
                "I would ask about the team's current challenges, success "
                "metrics for this role, and how the team works — questions my "
                "preparation for this posting raised."
            ),
            "competency_tag": "culture_fit",
        },
    ]
    return {"status": "complete", "questions": questions}


def generate_interview(
    cv_text: str,
    job_description: str,
    *,
    user_id: str,
    scan_id: str = "",
    company_name: str = "",
    grant_allowance: bool = True,
) -> dict[str, Any]:
    """Pro-gated, 4,000-credit mock interview (task 15.7)."""
    ledger = default_ledger()
    if not check_feature_access(ledger, user_id, FEATURE):
        raise FeatureNotAvailable(FEATURE, required_tier="pro", user_tier=tier_of(ledger, user_id))
    if grant_allowance:
        ensure_allowance(ledger, user_id)
    if ledger.balance(user_id) < INTERVIEW_COST:
        raise InsufficientCredits(ledger.balance(user_id), INTERVIEW_COST)

    with _store_lock:
        data = _load_all()
        cached = data["interviews"].get(scan_id) if scan_id else None
        if cached is not None and cached.get("prompt_version") == PROMPT_VERSION:
            return {**cached["payload"], "cached": True, "cost_charged": 0}

        resume = parse_resume(cv_text.encode("utf-8"), content_type="text/plain")
        payload = _deterministic_interview(resume, job_description, company_name)
        errors = validate(payload, _schema())
        if errors:  # pragma: no cover — fixed rows always conform
            raise VantiaError(f"interview payload violates schema: {errors}", code="schema_invalid")
        record = {
            "scan_id": scan_id,
            "payload": payload,
            "prompt_version": PROMPT_VERSION,
            "created_at": utc_now(),
            "artifact_hash": hashlib.sha256(str(payload).encode("utf-8")).hexdigest()[:16],
        }
        if scan_id:
            data["interviews"][scan_id] = record
            _save_all(data)

    entry = ledger.spend(
        user_id,
        INTERVIEW_COST,
        ref=f"mock_interview:{scan_id or record['artifact_hash']}",
        meta={"feature": FEATURE, "scan_id": scan_id},
    )
    return {**payload, "cached": False, "cost_charged": abs(int(entry["amount"]))}
