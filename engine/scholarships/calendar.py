"""Scholarship calendar export (task 15.10) — RFC 5545 (.ics).

One ``VEVENT`` per funded programme with a known application window; the
event day is the **window close** (the deadline a applicant must meet).
Month-precision windows (the database publishes ``YYYY-MM`` when the
official source gives month precision only) resolve to the last day of
that month and the event description says so — the calendar never
pretends to a precision the source does not publish.

Programmes whose window is ``None`` (varies by course/country) are
**skipped and reported** rather than given a fabricated date.

Validated by ``tests/test_scholarship_calendar.py`` against the RFC 5545
subset that Google Calendar, Apple Calendar and Outlook all import:
``VCALENDAR``/``VEVENT`` nesting, ``UID``/``DTSTAMP``/``DTSTART``/
``SUMMARY``, ``DATE``-value all-day events, TEXT escaping (\\, ;, ,, \\n)
and 75-octet line folding.
"""

from __future__ import annotations

import hashlib
from calendar import monthrange
from datetime import UTC, date, datetime
from typing import Any

from ..logging_config import utc_now
from .database import SCHOLARSHIPS, Scholarship

__all__ = ["build_calendar", "build_event", "calendar_for", "deadline_event_date"]

CALENDAR_NAME = "Vantia scholarship deadlines"
PRODUCT_ID = "-//Vantia//Scholarship Calendar 1.0//EN"


def _escape(text: str) -> str:
    """RFC 5545 TEXT escaping (§3.3.11)."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """RFC 5545 line folding: 75 **octets** per line, continuations start with a space."""
    if len(line.encode("utf-8")) <= 75:
        return line
    chunks: list[str] = []
    current = ""
    limit = 75
    for char in line:
        candidate = current + char
        if len(candidate.encode("utf-8")) > limit:
            chunks.append(current)
            current = char
            limit = 74  # continuation lines carry one leading space
        else:
            current = candidate
    if current:
        chunks.append(current)
    return ("\r\n" + " ").join(chunks)


def deadline_event_date(window_close: str) -> tuple[date, str] | None:
    """``YYYY-MM-DD`` → that date; ``YYYY-MM`` → month end + precision note.

    Anything else (``None``, unknown formats) → ``None`` (skip, never guess).
    """
    if not window_close:
        return None
    value = window_close.strip()
    try:
        if len(value) == 10:  # YYYY-MM-DD
            return date.fromisoformat(value), "day"
        if len(value) == 7:  # YYYY-MM
            year, month = int(value[:4]), int(value[5:7])
            last = monthrange(year, month)[1]
            return date(year, month, last), "month"
    except ValueError:
        return None
    return None


def build_event(sch: Scholarship, *, now: datetime | None = None) -> tuple[str, str] | None:
    """One VEVENT block for ``sch``; ``None`` when no deadline is known."""
    resolved = deadline_event_date(sch.window_close or "")
    if resolved is None:
        return None
    deadline, precision = resolved
    uid = f"{sch.id}@vantia-scholarships"
    dtstamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    description = (
        f"{sch.provider} — {sch.name}. Funding: {sch.funding.replace('_', ' ')}. "
        f"Level: {sch.level}. "
        + (
            "Deadline precision: month (official source publishes month only; "
            "this event marks the end of that month)."
            if precision == "month"
            else "Deadline precision: day (published by the official source)."
        )
        + (f" Basis: {sch.basis}" if sch.basis else "")
    )
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;VALUE=DATE:{deadline.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{date.fromordinal(deadline.toordinal() + 1).strftime('%Y%m%d')}",
        f"SUMMARY:{_escape(sch.name)} — applications close",
        f"DESCRIPTION:{_escape(description)}",
        f"URL:{sch.url}" if sch.url else None,
        "BEGIN:VALARM",
        "TRIGGER:-P7D",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_escape(sch.name)} closes in 7 days",
        "END:VALARM",
        "END:VEVENT",
    ]
    return "\r\n".join(_fold(line) for line in lines if line is not None), deadline.isoformat()


def build_calendar(
    scholarships: list[Scholarship] | None = None,
    *,
    now: datetime | None = None,
) -> tuple[str, dict[str, Any]]:
    """Full ``.ics`` document plus a report ``{events, skipped}``.

    ``skipped`` lists programme ids with no published deadline — the
    honest gap report (never a fabricated date).
    """
    items = scholarships if scholarships is not None else list(SCHOLARSHIPS)
    head = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODUCT_ID}",
        f"X-WR-CALNAME:{CALENDAR_NAME}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    events: list[str] = []
    skipped: list[str] = []
    for sch in items:
        built = build_event(sch, now=now)
        if built is None:
            skipped.append(sch.id)
        else:
            events.append(built[0])
    body = "\r\n".join(head + events + ["END:VCALENDAR"]) + "\r\n"
    report = {
        "events": len(events),
        "skipped": skipped,
        "generated_at": now.isoformat() if now else utc_now(),
        "calendar_hash": hashlib.sha256(body.encode("utf-8")).hexdigest()[:16],
    }
    return body, report


def calendar_for(
    scholarship_id: str, *, now: datetime | None = None
) -> tuple[str, dict[str, Any]] | None:
    """Single-programme calendar; ``None`` when the id is unknown."""
    for sch in SCHOLARSHIPS:
        if sch.id == scholarship_id:
            return build_calendar([sch], now=now)
    return None
