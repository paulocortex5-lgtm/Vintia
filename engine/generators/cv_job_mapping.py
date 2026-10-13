"""CV-to-job-specification mapping (task 15.5, Pro).

Where the ATS *score* says how well a CV fits a posting, the mapping says
**exactly what is missing and what to do about it**: one row per job
requirement with the CV evidence, a match/partial/gap verdict and a
concrete bridge suggestion.

Design (repo rules carried over):

* **Tier gate first (R16)** — :func:`engine.credits.tiers.check_feature_access`
  runs before any work; a free-tier user raises
  :class:`~engine.errors.FeatureNotAvailable` and spends nothing.
* **Deterministic-first** — the shipped mapping is computed from the
  existing keyword matcher (``job_keywords`` / ``gap_report`` / stems), so
  the feature works with zero providers online and every row traces to
  real text. An LLM polish (Pro chains) may rewrite the *phrasing* of
  bridge suggestions; it can never add rows the matcher did not find.
* **Persist then debit (R17)** — the artifact lands in the local-first
  store (and the Supabase mirror table when configured) *before* the
  6,000-credit debit; a failed run costs nothing (R18).
* **Idempotent** — same ``(scan_id, prompt_version)`` returns the cached
  artifact and moves no credits.
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

__all__ = ["MAPPING_COST", "generate_mapping", "load_mapping"]

LOGGER = logging.getLogger("vantia.generators.cv_job_mapping")

#: Credit price (task 15.5 §9.4).
MAPPING_COST = 6000

PROMPT_VERSION = "1.0.0"
FEATURE = "cv_job_mapping"

_store_lock = threading.RLock()


def _default_dir() -> str:
    return os.environ.get("VANTIA_FEATURES_DIR", os.path.join(".vantia", "features"))


def _schema() -> dict[str, Any]:
    schema = load_json("engine/schemas/cv_job_mapping.schema.json")
    if schema is None:  # pragma: no cover — packaged file must exist
        raise VantiaError("cv_job_mapping.schema.json missing", code="schema_missing")
    return schema


def _load_all() -> dict[str, Any]:
    data = load_json(os.path.join(_default_dir(), "cv_job_mappings.json"))
    if not isinstance(data, dict) or not isinstance(data.get("mappings"), dict):
        return {"version": 1, "mappings": {}}
    return data


def _save_all(data: dict[str, Any]) -> None:
    path = os.path.join(_default_dir(), "cv_job_mappings.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write_json(path, data)


def load_mapping(scan_id: str) -> dict[str, Any] | None:
    """Cached mapping payload for ``scan_id``, or None."""
    return _load_all()["mappings"].get(scan_id)


def _bridge_for(keyword: str) -> str:
    """Concrete, honest bridge action for one missing keyword."""
    return (
        f"Close the gap on “{keyword}”: add a recent project, course or "
        f"certification that used it, with one quantified outcome — then cite "
        f"it in the skills and experience sections."
    )


def _deterministic_map(
    resume: ParsedResume, job_description: str, ats_report: dict[str, Any] | None
) -> dict[str, Any]:
    """One mapping row per demanded keyword, from the real matcher (no LLM)."""
    keywords = job_keywords(job_description)
    resume_kws = resume_keywords(resume)
    matched = set(match_keywords(keywords, resume_kws)[0])
    rows: list[dict[str, Any]] = []
    for keyword in keywords:
        if keyword in matched:
            rows.append(
                {
                    "requirement": keyword,
                    "cv_evidence": f"“{keyword}” appears in the CV text.",
                    "match_level": "match",
                    "bridge_suggestion": "",
                }
            )
        else:
            near = [k for k in matched if k[:4] == keyword[:4] and len(k) >= 4]
            if near:
                rows.append(
                    {
                        "requirement": keyword,
                        "cv_evidence": f"Adjacent evidence: {', '.join(near[:3])}.",
                        "match_level": "partial",
                        "bridge_suggestion": _bridge_for(keyword),
                    }
                )
            else:
                rows.append(
                    {
                        "requirement": keyword,
                        "cv_evidence": "No evidence in the CV text.",
                        "match_level": "gap",
                        "bridge_suggestion": _bridge_for(keyword),
                    }
                )
    match_count = sum(1 for r in rows if r["match_level"] == "match")
    partial_count = sum(1 for r in rows if r["match_level"] == "partial")
    gap_count = sum(1 for r in rows if r["match_level"] == "gap")
    gaps = [r["requirement"] for r in rows if r["match_level"] == "gap"]
    return {
        "status": "complete",
        "mappings": rows,
        "match_count": match_count,
        "partial_count": partial_count,
        "gap_count": gap_count,
        "priority_gaps": gaps[:5],
    }


def generate_mapping(
    resume_text: str,
    job_description: str,
    *,
    user_id: str,
    scan_id: str = "",
    ats_report: dict[str, Any] | None = None,
    grant_allowance: bool = True,
) -> dict[str, Any]:
    """Pro-gated, 6,000-credit CV→job-spec mapping (task 15.5).

    Order (R16/R17/R18): tier gate → balance check → deterministic map →
    persist → debit. Idempotent per ``scan_id``.
    """
    ledger = default_ledger()
    if not check_feature_access(ledger, user_id, FEATURE):
        raise FeatureNotAvailable(FEATURE, required_tier="pro", user_tier=tier_of(ledger, user_id))
    if grant_allowance:
        ensure_allowance(ledger, user_id)
    if ledger.balance(user_id) < MAPPING_COST:
        raise InsufficientCredits(ledger.balance(user_id), MAPPING_COST)

    with _store_lock:
        data = _load_all()
        cached = data["mappings"].get(scan_id) if scan_id else None
        if cached is not None and cached.get("prompt_version") == PROMPT_VERSION:
            return {**cached["payload"], "cached": True, "cost_charged": 0}

        resume = parse_resume(resume_text.encode("utf-8"), content_type="text/plain")
        payload = _deterministic_map(resume, job_description, ats_report)
        errors = validate(payload, _schema())
        if errors:  # pragma: no cover — deterministic rows always conform
            raise VantiaError(f"mapping payload violates schema: {errors}", code="schema_invalid")

        record = {
            "scan_id": scan_id,
            "payload": payload,
            "prompt_version": PROMPT_VERSION,
            "created_at": utc_now(),
            "artifact_hash": hashlib.sha256(str(payload).encode("utf-8")).hexdigest()[:16],
        }
        if scan_id:
            data["mappings"][scan_id] = record
            _save_all(data)

    # Persist first, debit after (R17).
    entry = ledger.spend(
        user_id,
        MAPPING_COST,
        ref=f"cv_job_mapping:{scan_id or record['artifact_hash']}",
        meta={"feature": FEATURE, "scan_id": scan_id},
    )
    return {**payload, "cached": False, "cost_charged": abs(int(entry["amount"]))}
