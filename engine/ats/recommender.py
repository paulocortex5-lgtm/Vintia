"""Job recommendations from CV (task 15.1).

Ranks the verified job pool against a parsed CV and returns the top 20.
Fully deterministic — no LLM, no network: the match is a weighted blend of
six sub-scores computed from facts the parser and the ingest store already
hold, so it works even when every provider is down and costs zero credits.

Weights (§5.2), summing to 1.0:

* ``skill``      0.35 — cosine similarity between the CV skill vector and
  the job skill vector, using the existing keyword taxonomy
  (:mod:`engine.ats.keywords` — normalise + stem + synonyms).
* ``experience`` 0.20 — CV dated years vs the job's stated minimum
  (``N years`` in the description); jobs with no stated minimum score 1.0.
* ``education``  0.15 — highest parsed credential vs the job's stated
  requirement (bachelor / master / phd keywords).
* ``location``   0.10 — job country vs the user's selected countries.
* ``visa``       0.10 — the job is flagged ``visa_sponsorship``.
* ``recency``    0.10 — posted within the last 7 days, linearly decaying.

Caching (R24): results are cached by ``sha256(cv_hash + filters)`` for
24 hours in ``$VANTIA_INGEST_DIR/recommendations.json``; an identical
request inside the TTL returns ``{"cached": true}`` with no recomputation.

Fallback (§5.2): when the CV cannot be parsed (image-only PDF, empty
text), the most recent 20 verified jobs for the filters are returned with
``note`` explaining why the list is generic — never an error page.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from ..json_utils import atomic_write_json, load_json
from ..logging_config import utc_now
from .keywords import normalise, stem
from .parser import ParsedResume

__all__ = [
    "MATCH_WEIGHTS",
    "RECOMMENDATION_LIMIT",
    "RecommendationResult",
    "recommend",
]

LOGGER = logging.getLogger("vantia.ats.recommender")

#: §5.2 weights.
MATCH_WEIGHTS: dict[str, float] = {
    "skill": 0.35,
    "experience": 0.20,
    "education": 0.15,
    "location": 0.10,
    "visa": 0.10,
    "recency": 0.10,
}

RECOMMENDATION_LIMIT = 20
CACHE_TTL_HOURS = 24

_YEARS_RE = re.compile(r"(\d+)\s*\+?\s*(?:-?\s*\d+)?\s*(?:years?|yrs?)\b", re.IGNORECASE)
_EDU_ORDER = ("phd", "doctor", "master", "bachelor", "degree")
_EDU_RANK = {"phd": 3, "doctor": 3, "master": 2, "bachelor": 1, "degree": 1}


def _cache_path(store_dir: str | None = None) -> str:
    base = store_dir or os.environ.get("VANTIA_INGEST_DIR", os.path.join(".vantia", "ingest"))
    return os.path.join(base, "recommendations.json")


@dataclass(frozen=True)
class RecommendationResult:
    """One ranked job with its score and a human-readable rationale."""

    job_id: str
    match_score: float
    matched_skills: list[str]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "match_score": round(self.match_score, 4),
            "matched_skills": self.matched_skills,
            "rationale": self.rationale,
        }


def _token_set(words: list[str]) -> set[str]:
    """Normalised + stemmed token set (shared with the keyword matcher)."""
    out: set[str] = set()
    for word in words:
        token = stem(normalise(word))
        if token:
            out.add(token)
    return out


def _cosine(a: set[str], b: set[str]) -> float:
    """Cosine similarity of two sets treated as 0/1 vectors."""
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    return overlap / math.sqrt(len(a) * len(b))


def _job_skill_tokens(job: dict[str, Any]) -> set[str]:
    text = f"{job.get('title', '')} {job.get('description', '')}"
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", text)]
    return _token_set(words)


def _experience_score(resume: ParsedResume, job: dict[str, Any]) -> float:
    match = _YEARS_RE.search(job.get("description") or "")
    if not match:
        return 1.0  # no stated minimum — no gap to close
    required = float(match.group(1))
    have = resume.years_experience
    if have >= required:
        return 1.0
    if required == 0:
        return 1.0
    return max(0.0, have / required)


def _education_rank(words: str) -> int:
    lowered = words.lower()
    rank = 0
    for token in _EDU_ORDER:
        if token in lowered:
            rank = max(rank, _EDU_RANK[token])
    return rank


def _education_score(resume: ParsedResume, job: dict[str, Any]) -> float:
    required = _education_rank(job.get("description") or "")
    if required == 0:
        return 1.0
    have = _education_rank(" ".join(str(e) for e in resume.education))
    if have == 0:
        return 0.5  # unknown credential: honest partial, never a silent full match
    return 1.0 if have >= required else have / required


def _location_score(job: dict[str, Any], countries: list[str]) -> float:
    if not countries:
        return 1.0
    return 1.0 if (job.get("country") or "").upper() in {c.upper() for c in countries} else 0.0


def _visa_score(job: dict[str, Any]) -> float:
    return 1.0 if job.get("visa_sponsorship") is True else 0.0


def _recency_score(job: dict[str, Any], now: datetime) -> float:
    posted = job.get("posted_at")
    if not posted:
        return 0.5  # unknown date: neutral, neither boosted nor punished
    try:
        age_days = (now.date() - datetime.fromisoformat(posted).date()).days
    except ValueError:
        return 0.5
    if age_days <= 0:
        return 1.0
    if age_days >= 7:
        return 0.0
    return 1.0 - (age_days / 7.0)


def _cache_key(cv_hash: str, filters: dict[str, Any]) -> str:
    payload = json.dumps({"cv": cv_hash, "filters": filters}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_cache(now: datetime) -> dict[str, dict[str, Any]]:
    data = load_json(_cache_path())
    if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
        return {}
    entries = data["entries"]
    fresh: dict[str, dict[str, Any]] = {}
    ttl = timedelta(hours=CACHE_TTL_HOURS)
    for key, entry in entries.items():
        try:
            created = datetime.fromisoformat(entry["created_at"])
        except (KeyError, ValueError):
            continue
        if now - created < ttl:
            fresh[key] = entry
    return fresh


def _store_cache(key: str, entry: dict[str, Any], now: datetime) -> None:
    entries = _load_cache(now)
    entries[key] = {**entry, "created_at": now.isoformat()}
    path = _cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write_json(path, {"version": 1, "entries": entries, "saved_at": utc_now()})


def recommend(
    resume: ParsedResume | None,
    *,
    filters: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return the top-20 job recommendations for ``resume`` under ``filters``.

    ``filters`` supports ``countries`` (list of ISO2) and ``role`` (title
    substring). Free tier, no credits (§5.6). Returns::

        {"jobs": [{"job_id", "match_score", "matched_skills",
                   "rationale", "title", "company", "country",
                   "posted_at", "apply_url", "link_status"}],
         "cached": bool, "note": str}
    """
    from ..sources.ingest_store import search_jobs

    current = now or datetime.now(UTC)
    filters = filters or {}
    countries = [str(c) for c in filters.get("countries", []) or []]
    role = str(filters.get("role") or "")

    pool = search_jobs(country=None, role=None)
    if countries:
        pool = [
            j for j in pool if (j.get("country") or "").upper() in {c.upper() for c in countries}
        ]
    if role:
        pool = [j for j in pool if role.casefold() in (j.get("title") or "").casefold()]

    parseable = resume is not None and bool((resume.raw_text or "").strip())
    if parseable and resume is not None:
        cv_hash = hashlib.sha256(resume.raw_text.encode("utf-8")).hexdigest()
    else:
        cv_hash = "no-cv"
    key = _cache_key(cv_hash, {"countries": countries, "role": role})
    cached_entry = _load_cache(current).get(key)
    if cached_entry is not None:
        return {"jobs": cached_entry["jobs"], "cached": True, "note": cached_entry.get("note", "")}

    def _brief(job: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": f"{job.get('portal')}:{job.get('external_id')}",
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "country": job.get("country", ""),
            "location": job.get("location", ""),
            "posted_at": job.get("posted_at"),
            "apply_url": job.get("apply_url", ""),
            "link_status": job.get("link_status", ""),
            "visa_sponsorship": job.get("visa_sponsorship"),
        }

    note = ""
    if not parseable:
        # Fallback (§5.2): generic recency-ranked list, honestly explained.
        note = (
            "Your CV could not be parsed (for example an image-only PDF), "
            "so these are the most recent verified jobs for your filters — "
            "not personalised matches. Upload a text-based PDF/DOCX for "
            "ranked recommendations."
        )
        generic = [_brief(j) for j in pool[:RECOMMENDATION_LIMIT]]
        for item in generic:
            item.update(
                {"match_score": 0.0, "matched_skills": [], "rationale": "generic (CV unparseable)"}
            )
        result = {"jobs": generic, "cached": False, "note": note}
        _store_cache(key, result, current)
        return result

    assert resume is not None  # narrows: parseable is True past the fallback

    cv_skills = _token_set(list(resume.skills) + list(resume.certifications))
    if not cv_skills:
        cv_skills = _token_set(
            [w for w in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", resume.raw_text)]
        )

    ranked: list[RecommendationResult] = []
    briefs: dict[str, dict[str, Any]] = {}
    for job in pool:
        job_skills = _job_skill_tokens(job)
        overlap = sorted(cv_skills & job_skills)
        skill = _cosine(cv_skills, job_skills)
        score = (
            MATCH_WEIGHTS["skill"] * skill
            + MATCH_WEIGHTS["experience"] * _experience_score(resume, job)
            + MATCH_WEIGHTS["education"] * _education_score(resume, job)
            + MATCH_WEIGHTS["location"] * _location_score(job, countries)
            + MATCH_WEIGHTS["visa"] * _visa_score(job)
            + MATCH_WEIGHTS["recency"] * _recency_score(job, current)
        )
        job_id = f"{job.get('portal')}:{job.get('external_id')}"
        rationale_bits = []
        if overlap:
            rationale_bits.append(f"{len(overlap)} shared skills")
        if job.get("visa_sponsorship"):
            rationale_bits.append("sponsorship flagged")
        if _experience_score(resume, job) >= 1.0:
            rationale_bits.append("meets experience minimum")
        ranked.append(
            RecommendationResult(
                job_id=job_id,
                match_score=score,
                matched_skills=overlap[:3],
                rationale=", ".join(rationale_bits) or "partial keyword overlap",
            )
        )
        briefs[job_id] = _brief(job)

    ranked.sort(key=lambda r: (-r.match_score, r.job_id))
    top = ranked[:RECOMMENDATION_LIMIT]
    jobs = [{**briefs[r.job_id], **r.to_dict()} for r in top]
    result = {"jobs": jobs, "cached": False, "note": note}
    _store_cache(key, result, current)
    return result
