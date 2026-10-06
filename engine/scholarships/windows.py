"""Application window tracker (task 3.5).

Statuses, always against an explicit ``today`` (tests inject theirs):

* ``open``      — inside the application window (``days_left`` counts down)
* ``upcoming``  — window not opened yet (``days_until_open``)
* ``closed``     — this cycle finished; ``next_opens`` shows the annual rerun
* ``unknown``    — no window embedded (varies by course/country) — the UI
  says "check the official page" instead of inventing a deadline

Windows may be month-precision (``"YYYY-MM"``, as published by official
timelines) or day-precision (``"YYYY-MM-DD"``); month-precision close
dates mean *the whole closing month*. Annual windows recur on
month/day, matching how these programmes actually run their cycles.
"""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime

from .database import SCHOLARSHIPS, Scholarship

__all__ = ["open_windows", "window_status", "windows"]

_EOM_DAY = 99  # sentinel: "last day of the month" for month-precision closes


def _as_date(value: str) -> tuple[int, int, int | None]:
    parts = value.split("-")
    year, month = int(parts[0]), int(parts[1])
    day = int(parts[2]) if len(parts) > 2 else None
    return year, month, day


def _window_bounds(sch: Scholarship) -> tuple[tuple[int, int], tuple[int, int], str] | None:
    """(open_md, close_md, precision) with month-precision normalised."""
    if not sch.window_open or not sch.window_close:
        return None
    _, om, od = _as_date(sch.window_open)
    _, cm, cd = _as_date(sch.window_close)
    precision = "day" if od is not None and cd is not None else "month"
    open_md = (om, od if od is not None else 1)
    close_md = (cm, cd if cd is not None else _EOM_DAY)
    return open_md, close_md, precision


def window_status(sch: Scholarship, today: date | None = None) -> dict[str, object]:
    """Window state of one program for ``today`` (UTC calendar date)."""
    current = today or datetime.now(UTC).date()
    bounds = _window_bounds(sch)
    base: dict[str, object] = {
        "id": sch.id,
        "name": sch.name,
        "url": sch.url,
        "annual": sch.annual,
        "opens": None,
        "closes": None,
        "days_left": None,
        "days_until_open": None,
        "next_opens": None,
        "precision": None,
        "note": "",
    }
    if bounds is None:
        base["status"] = "unknown"
        base["note"] = (
            "no recurring window is embedded for this programme "
            "(deadlines vary by course/country) — check the official page"
        )
        return base

    open_md, close_md, precision = bounds
    base["precision"] = precision

    if not sch.annual:
        return _fixed_status(sch, base, current)

    # unified annual logic: works for same-year and year-wrapping windows
    prev_open, next_open = _around(open_md, current, precision)
    prev_close, next_close = _around(close_md, current, precision, inclusive_next=True)
    if prev_open is not None and next_close is not None and next_close < (next_open or date.max):
        # inside a cycle: its close is still ahead, before the next open
        opens = prev_open
        closes = next_close
        base.update(status="open", opens=opens.isoformat(), closes=closes.isoformat())
        base["days_left"] = (closes - current).days
        return base

    if next_open is None:
        base["status"] = "unknown"
        base["note"] = "window could not be resolved — check the official page"
        return base

    # between cycles: recently-finished → closed, approaching → upcoming
    since_close = (current - prev_close).days if prev_close else None
    to_open = (next_open - current).days
    if since_close is not None and since_close < to_open:
        base["status"] = "closed"
        base["next_opens"] = next_open.isoformat()
        base["closes"] = prev_close.isoformat() if prev_close else None
    else:
        base["status"] = "upcoming"
        base["opens"] = next_open.isoformat()
        base["days_until_open"] = to_open
    return base


def _around(
    md: tuple[int, int], today: date, precision: str, *, inclusive_next: bool = False
) -> tuple[date | None, date | None]:
    """(most recent occurrence ≤ today, next occurrence >|= today) for month/day.

    ``inclusive_next`` is for close dates: the closing day itself is
    still ``open``, so the "next close" must be allowed to equal today.
    """
    occurrences = [
        _concrete(year, md, precision) for year in (today.year - 1, today.year, today.year + 1)
    ]
    prev = max((d for d in occurrences if d <= today), default=None)
    if inclusive_next:
        nxt = min((d for d in occurrences if d >= today), default=None)
    else:
        nxt = min((d for d in occurrences if d > today), default=None)
    return prev, nxt


def _concrete(year: int, md: tuple[int, int], precision: str) -> date:
    month, day = md
    if day == _EOM_DAY:
        return date(year, month, calendar.monthrange(year, month)[1])
    if precision == "month" and day > calendar.monthrange(year, month)[1]:
        return date(year, month, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _fixed_status(sch: Scholarship, base: dict[str, object], current: date) -> dict[str, object]:
    """Non-recurring window: absolute dates, no rerun."""
    assert sch.window_open is not None and sch.window_close is not None
    oy, om, od = _as_date(sch.window_open)
    cy, cm, cd = _as_date(sch.window_close)
    opens = date(oy, om, od or 1)
    closes = date(cy, cm, cd or calendar.monthrange(cy, cm)[1])
    base["opens"], base["closes"] = opens.isoformat(), closes.isoformat()
    if current < opens:
        base["status"] = "upcoming"
        base["days_until_open"] = (opens - current).days
    elif current <= closes:
        base["status"] = "open"
        base["days_left"] = (closes - current).days
    else:
        base["status"] = "closed"
    return base


def windows(
    today: date | None = None, scholarships: tuple[Scholarship, ...] | None = None
) -> list[dict[str, object]]:
    """Status of every program (registry order)."""
    rows = scholarships if scholarships is not None else SCHOLARSHIPS
    return [window_status(row, today) for row in rows]


def open_windows(
    today: date | None = None, scholarships: tuple[Scholarship, ...] | None = None
) -> list[dict[str, object]]:
    """Only the programs accepting applications on ``today``."""
    return [row for row in windows(today, scholarships) if row["status"] == "open"]
