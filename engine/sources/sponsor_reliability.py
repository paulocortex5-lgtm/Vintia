"""Sponsor reliability scoring (task 15.4).

For every company on a country's sponsor register, compute a 0-100
reliability score so users can prioritise trustworthy employers. The
formula and weights are exactly §8.2; every component is computed from
signals the platform actually has, and a signal that does not exist yet
scores **neutral 0.5** with the record's ``note`` saying so — nothing is
invented (repo honesty rules).

Signals (local-first, git-authoritative under ``$VANTIA_INGEST_DIR``):

* ``tenure_months``  — months the company has been present in the weekly
  register snapshots kept by :func:`record_snapshot` (0.30)
* ``sponsorships_12m`` — approved sponsored hires in the last 12 months;
  not published by the offline registers, so neutral until a register
  carrying counts is wired in (0.25)
* ``consistency`` — fraction of observed snapshots the company appeared
  in; a company present in the current snapshot with no history scores
  1.0 ("here now, no history to contradict it") (0.20)
* ``failed_count`` — revocations/failed sponsorships; unknown → zero
  penalty (0.15)
* ``user_signal`` — aggregate Vantia user ratings from
  ``sponsor_ratings.json``; no ratings → neutral 0.5 (0.10)

Weekly rebuild: ``.github/workflows/sponsor-reliability.yml`` runs
``python -m engine.sources.sponsor_reliability`` (cron Sunday 03:00 UTC).

Badge (§8.5): use :func:`reliability_badge` — green ≥75, amber 50-74,
red <50.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from ..json_utils import atomic_write_json, load_json
from ..logging_config import utc_now

__all__ = [
    "RELIABILITY_WEIGHTS",
    "SponsorScore",
    "compute_score",
    "load_scores",
    "rebuild",
    "record_snapshot",
    "reliability_badge",
    "score_for",
]

LOGGER = logging.getLogger("vantia.sources.sponsor_reliability")

#: §8.2 weights.
RELIABILITY_WEIGHTS: dict[str, float] = {
    "tenure": 0.30,
    "volume": 0.25,
    "consistency": 0.20,
    "volatility": 0.15,
    "user_signal": 0.10,
}

#: Tenure saturates at this many months (2 years on the register = full marks).
TENURE_SATURATION_MONTHS = 24
#: Volume saturates at this many approved hires in 12 months.
VOLUME_SATURATION = 500

_store_lock = threading.RLock()


def _default_dir() -> str:
    return os.environ.get("VANTIA_INGEST_DIR", os.path.join(".vantia", "ingest"))


def _path(store_dir: str | None = None) -> str:
    return os.path.join(store_dir or _default_dir(), "sponsor_reliability.json")


def _ratings_path(store_dir: str | None = None) -> str:
    return os.path.join(store_dir or _default_dir(), "sponsor_ratings.json")


@dataclass
class SponsorScore:
    """One company's reliability record (§8.3 columns + provenance)."""

    company_name: str
    country: str
    score: int
    tenure_months: int
    sponsorships_12m: int
    failed_count: int
    consistency: float
    user_signal: float
    note: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _months_between(start: str, end: str) -> int:
    try:
        a = datetime.fromisoformat(start)
        b = datetime.fromisoformat(end)
    except ValueError:
        return 0
    return max(0, (b.year - a.year) * 12 + (b.month - a.month))


def compute_score(
    company_name: str,
    country: str,
    *,
    history: list[str],
    observed: int | None = None,
    sponsorships_12m: int | None = None,
    failed_count: int | None = None,
    user_signal: float | None = None,
    now: datetime | None = None,
) -> SponsorScore:
    """Compute the §8.2 score from observed snapshot ``history`` (ISO dates).

    Unknown components score neutral 0.5 (volume, user signal) or neutral
    no-penalty (volatility) and the record's ``note`` says which.
    """
    current = (now or datetime.now(UTC)).date()
    history = sorted(set(history))
    tenure_months = _months_between(history[0], current.isoformat()) if history else 0
    months_seen = len(history)
    months_observed = max(months_seen, observed or months_seen, 1)
    consistency = min(1.0, months_seen / months_observed)

    tenure_component = min(1.0, tenure_months / TENURE_SATURATION_MONTHS)
    if sponsorships_12m is None:
        volume_component = 0.5
    else:
        volume_component = min(1.0, max(0.0, sponsorships_12m / VOLUME_SATURATION))
    if failed_count is None or (sponsorships_12m or 0) + (failed_count or 0) == 0:
        volatility_component = 1.0  # no observed failures → no penalty
    else:
        failures = failed_count / ((sponsorships_12m or 0) + failed_count)
        volatility_component = 1.0 - min(1.0, failures)
    user_component = 0.5 if user_signal is None else min(1.0, max(0.0, user_signal))

    total = (
        RELIABILITY_WEIGHTS["tenure"] * tenure_component
        + RELIABILITY_WEIGHTS["volume"] * volume_component
        + RELIABILITY_WEIGHTS["consistency"] * consistency
        + RELIABILITY_WEIGHTS["volatility"] * volatility_component
        + RELIABILITY_WEIGHTS["user_signal"] * user_component
    )
    notes = []
    if sponsorships_12m is None:
        notes.append("hire volume unknown — neutral")
    if user_signal is None:
        notes.append("no user ratings yet — neutral")
    if failed_count is None:
        notes.append("no revocation data — no penalty")
    return SponsorScore(
        company_name=company_name,
        country=country,
        score=round(total * 100),
        tenure_months=tenure_months,
        sponsorships_12m=sponsorships_12m or 0,
        failed_count=failed_count or 0,
        consistency=round(consistency, 3),
        user_signal=round(user_component, 3),
        note="; ".join(notes),
        updated_at=utc_now(),
    )


def _load_store(store_dir: str | None = None) -> dict[str, Any]:
    data = load_json(_path(store_dir))
    if not isinstance(data, dict):
        return {"version": 1, "snapshot_dates": [], "companies": {}}
    data.setdefault("snapshot_dates", [])
    data.setdefault("companies", {})
    return data


def _save_store(data: dict[str, Any], store_dir: str | None = None) -> str:
    path = _path(store_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write_json(path, data)
    return path


def record_snapshot(
    country: str,
    company_names: list[str],
    *,
    snapshot_date: str | None = None,
    store_dir: str | None = None,
) -> int:
    """Record one register snapshot: append the date to each company's history.

    Idempotent per (company, date). Returns how many companies now have a
    history entry for this snapshot.
    """
    day = snapshot_date or datetime.now(UTC).date().isoformat()
    with _store_lock:
        data = _load_store(store_dir)
        if day not in data["snapshot_dates"]:
            data["snapshot_dates"].append(day)
        touched = 0
        for name in company_names:
            key = f"{country}:{name}"
            entry = data["companies"].get(key)
            if entry is None:
                entry = {
                    "company_name": name,
                    "country": country,
                    "history": [],
                    "sponsorships_12m": None,
                    "failed_count": None,
                }
                data["companies"][key] = entry
            if day not in entry["history"]:
                entry["history"].append(day)
                touched += 1
        _save_store(data, store_dir)
    return touched


def load_scores(store_dir: str | None = None) -> dict[str, dict[str, Any]]:
    """All computed scores keyed by ``{country}:{company}``."""
    data = load_json(_path(store_dir))
    if not isinstance(data, dict) or not isinstance(data.get("scores"), dict):
        return {}
    return data["scores"]


def score_for(
    company_name: str,
    country: str,
    *,
    store_dir: str | None = None,
) -> dict[str, Any] | None:
    """One company's cached score, or None when it was never scored."""
    return load_scores(store_dir).get(f"{country}:{company_name}")


def rebuild(store_dir: str | None = None, *, now: datetime | None = None) -> dict[str, int]:
    """Recompute every score from the recorded snapshots (weekly cron).

    User ratings come from ``sponsor_ratings.json``:
    ``{key: {"ratings": [ints 1-5], "failed": int, "sponsorships_12m": int}}``.
    """
    current = now or datetime.now(UTC)
    data = _load_store(store_dir)
    ratings = load_json(_ratings_path(store_dir)) or {}
    if not isinstance(ratings, dict):
        ratings = {}
    observed = len(data["snapshot_dates"])
    scores: dict[str, dict[str, Any]] = {}
    for key, entry in data["companies"].items():
        extra = ratings.get(key) or {}
        user_signal = None
        raw = extra.get("ratings")
        if isinstance(raw, list) and raw:
            user_signal = (sum(int(r) for r in raw) / len(raw)) / 5.0
        record = compute_score(
            entry["company_name"],
            entry["country"],
            history=entry.get("history", []),
            observed=observed,
            sponsorships_12m=extra.get("sponsorships_12m", entry.get("sponsorships_12m")),
            failed_count=extra.get("failed", entry.get("failed_count")),
            user_signal=user_signal,
            now=current,
        )
        scores[key] = record.to_dict()
    out = {
        "version": 1,
        "snapshot_dates": data["snapshot_dates"],
        "companies": data["companies"],
        "scores": scores,
        "computed_at": utc_now(),
    }
    _save_store(out, store_dir)
    return {
        "scored": len(scores),
        "snapshots": observed,
        "rated": sum(1 for v in scores.values() if v.get("user_signal") != 0.5),
    }


def reliability_badge(score: int | None) -> dict[str, str]:
    """§8.5 colour-coded badge payload for job cards."""
    if score is None:
        return {"label": "Reliability: unknown", "tone": "neutral"}
    if score >= 75:
        tone = "green"
    elif score >= 50:
        tone = "amber"
    else:
        tone = "red"
    return {"label": f"Reliability: {score}/100", "tone": tone}


def main(argv: list[str] | None = None) -> int:
    """CLI for the weekly ``sponsor-reliability`` cron (§8.4)."""
    parser = argparse.ArgumentParser(description="Rebuild sponsor reliability scores")
    parser.add_argument("--store-dir", default=None)
    args = parser.parse_args(argv)
    stats = rebuild(args.store_dir)
    print(json.dumps(stats, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised by the cron only
    sys.exit(main())
