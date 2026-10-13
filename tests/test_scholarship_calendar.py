"""Scholarship calendar export tests (task 15.14 §14.4).

RFC 5545 structure, TEXT escaping, line folding, day/month precision and
the honest skip list for programmes without published deadlines. The
generated file must import into Google/Apple/Outlook — those all require
VCALENDAR/VEVENT nesting, UID/DTSTAMP/DTSTART and CRLF endings, which is
what is asserted here.
"""

from datetime import UTC, date, datetime

from engine.scholarships.calendar import (
    build_calendar,
    build_event,
    calendar_for,
    deadline_event_date,
)
from engine.scholarships.database import SCHOLARSHIPS, Scholarship


def _sch(**overrides):
    base = {
        "id": "test-prog",
        "name": "Test Scholarship",
        "provider": "Test Provider",
        "host_countries": ("GB",),
        "level": "masters",
        "min_eqf_level": 6,
        "fields": ("any",),
        "funding": "fully_funded",
        "nationality": ("any",),
        "window_open": "2026-09-01",
        "window_close": "2026-11-15",
        "annual": True,
        "url": "https://example.com/scholarship",
        "basis": "unit fixture",
    }
    base.update(overrides)
    return Scholarship(**base)


def test_deadline_event_date_day_precision():
    resolved = deadline_event_date("2026-11-15")
    assert resolved == (date(2026, 11, 15), "day")


def test_deadline_event_date_month_precision_uses_month_end():
    resolved = deadline_event_date("2026-02")
    assert resolved == (date(2026, 2, 28), "month")
    leap = deadline_event_date("2028-02")
    assert leap == (date(2028, 2, 29), "month")


def test_deadline_event_date_refuses_garbage():
    assert deadline_event_date("") is None
    assert deadline_event_date("soon") is None
    assert deadline_event_date("2026-13-45") is None


def test_calendar_has_valid_rfc_structure():
    body, report = build_calendar()
    assert body.startswith("BEGIN:VCALENDAR\r\n")
    assert body.endswith("END:VCALENDAR\r\n")
    assert "VERSION:2.0" in body
    assert "PRODID:" in body
    assert body.count("BEGIN:VEVENT") == body.count("END:VEVENT") == report["events"]
    # every event carries the required properties
    for prop in ("UID:", "DTSTAMP:", "DTSTART;VALUE=DATE:", "SUMMARY:"):
        assert body.count(prop) == report["events"]


def test_programmes_without_windows_are_skipped_and_reported():
    body, report = build_calendar()
    assert report["skipped"], "the shipped database has programmes without windows"
    for sch_id in report["skipped"]:
        assert sch_id not in body  # no fabricated dates, ever
    known = {s.id for s in SCHOLARSHIPS if s.window_close}
    assert report["events"] == len(known)


def test_month_precision_windows_are_annotated():
    month_only = _sch(window_close="2026-06")
    body, report = build_calendar([month_only])
    assert report["events"] == 1
    assert "DTSTART;VALUE=DATE:20260630" in body  # June has 30 days
    assert "month" in body  # precision note in the DESCRIPTION


def test_text_escaping_and_folding():
    tricky = _sch(
        id="tricky",
        name='Awards, Grants; and "Quotes"\nSecond Line',
        window_close="2026-05-01",
    )
    body, _ = build_calendar([tricky])
    for line in body.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75, f"line not folded: {line!r}"
    # unfold (RFC 5545 §3.1) before checking content — folding may split anywhere
    unfolded = body.replace("\r\n ", "")
    assert "Awards\\, Grants\\; and" in unfolded
    assert '"Quotes"\\nSecond' in unfolded  # escaped newline sits where the real one was


def test_event_day_after_deadline_is_dtend():
    sch = _sch(window_close="2026-11-15")
    built = build_event(sch, now=datetime(2026, 1, 1, tzinfo=UTC))
    assert built is not None
    block, day = built
    assert day == "2026-11-15"
    assert "DTEND;VALUE=DATE:20261116" in block


def test_single_programme_calendar_and_unknown_id():
    built = calendar_for("chevening")
    assert built is not None
    body, report = built
    assert report["events"] == 1
    assert "Chevening" in body
    assert calendar_for("does-not-exist") is None


def test_all_shipped_programmes_round_trip():
    """Every programme with a window must produce one importable event."""
    with_windows = [s for s in SCHOLARSHIPS if s.window_close]
    body, report = build_calendar(with_windows)
    assert report["events"] == len(with_windows)
    assert report["skipped"] == []
    assert body.count("BEGIN:VEVENT") == len(with_windows)
