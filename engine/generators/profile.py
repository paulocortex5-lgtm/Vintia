"""Resume profile loading (task 2.8 support).

The ATS resume generator (task 2.7) needs a :class:`CandidateProfile`;
the job pipeline (task 2.8) receives a ``resume_path`` from the caller.
This module bridges the two with two supported formats:

* **``.json``** — an explicit profile document (the precise path;
  unknown keys are ignored, ``skills`` may be a list of strings or
  ``{"name": ...}`` objects);
* **``.md`` / ``.txt``** — plain-text resumes parsed heuristically:
  the first ``#`` heading becomes the name, a ``Skills`` section
  (bullet or comma list) becomes the skill set, and the remaining
  prose becomes the summary.

Anything else refuses loudly (``code="profile_format_unsupported"``)
rather than guessing — a wrong parse silently producing a bad resume
is worse than a clear error.
"""

from __future__ import annotations

import json
import os
import re

from ..errors import VantiaError
from .resume import CandidateProfile, Education, Experience

__all__ = ["load_profile"]

_JSON_FIELDS = frozenset(
    {
        "name",
        "title",
        "email",
        "phone",
        "location",
        "summary",
        "skills",
        "experience",
        "education",
        "languages",
    }
)

_SKILLS_HEADING = re.compile(r"^\s*#{0,6}\s*skills\b[:\s]*$", re.IGNORECASE | re.MULTILINE)
_BULLET = re.compile(r"^\s*[-*•]\s+(.*)$")

#: headings that open a section, never a person's job title
_SECTION_HEADINGS = frozenset(
    {
        "skills",
        "experience",
        "education",
        "employment",
        "work experience",
        "projects",
        "summary",
        "contact",
        "references",
        "languages",
        "certifications",
        "awards",
    }
)


def load_profile(path: str) -> CandidateProfile:
    """Build a :class:`CandidateProfile` from a JSON or markdown/text file.

    Raises :class:`~engine.errors.VantiaError` (``profile_file_missing``,
    ``profile_format_unsupported``, ``profile_parse_error``) on anything
    the parser cannot honestly interpret.
    """
    if not os.path.exists(path):
        raise VantiaError(f"resume file not found: {path}", code="profile_file_missing", path=path)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        return _from_json(path)
    if ext in {".md", ".markdown", ".txt"}:
        return _from_text(path)
    raise VantiaError(
        f"unsupported resume format {ext!r} (expected .json, .md or .txt)",
        code="profile_format_unsupported",
        path=path,
    )


# ── JSON ───────────────────────────────────────────────────────────────


def _from_json(path: str) -> CandidateProfile:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise VantiaError(
            f"invalid JSON in {path}: {exc}", code="profile_parse_error", path=path
        ) from exc
    if not isinstance(data, dict):
        raise VantiaError(
            f"profile JSON must be an object, got {type(data).__name__}",
            code="profile_parse_error",
            path=path,
        )
    known = {k: v for k, v in data.items() if k in _JSON_FIELDS}
    known.setdefault("name", "")
    known.setdefault("title", "")
    known["skills"] = _str_tuple(known.get("skills"))
    known["languages"] = _str_tuple(known.get("languages"))
    known["experience"] = tuple(
        _experience(item) for item in _as_list(known.get("experience"), "experience", path)
    )
    known["education"] = tuple(
        _education(item) for item in _as_list(known.get("education"), "education", path)
    )
    for field in ("name", "title", "email", "phone", "location", "summary"):
        value = known.get(field, "")
        if value is None:
            known[field] = ""
        elif not isinstance(value, str):
            raise VantiaError(
                f"profile field {field!r} must be a string", code="profile_parse_error", path=path
            )
    return CandidateProfile(**known)  # type: ignore[arg-type]


def _as_list(value: object, field: str, path: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise VantiaError(
            f"profile field {field!r} must be a list", code="profile_parse_error", path=path
        )
    return value


def _str_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                out.append(item.strip())
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                out.append(item["name"].strip())
        return tuple(out)
    return ()


def _experience(item: object) -> Experience:
    if isinstance(item, str):
        return Experience(role=item, org="")
    if not isinstance(item, dict):
        return Experience(role="", org="")
    summaries = item.get("summary") or ()
    if isinstance(summaries, str):
        summaries = (summaries,)
    return Experience(
        role=str(item.get("role", "")),
        org=str(item.get("org", "")),
        start=str(item.get("start", "")),
        end=str(item.get("end", "")),
        summary=tuple(str(s) for s in summaries),
    )


def _education(item: object) -> Education:
    if isinstance(item, str):
        return Education(degree=item, school="")
    if not isinstance(item, dict):
        return Education(degree="", school="")
    return Education(
        degree=str(item.get("degree", "")),
        school=str(item.get("school", "")),
        year=str(item.get("year", "")),
    )


# ── markdown / plain text ──────────────────────────────────────────────


def _from_text(path: str) -> CandidateProfile:
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:  # pragma: no cover — raced deletion
        raise VantiaError(
            f"cannot read resume file {path}: {exc}", code="profile_file_missing", path=path
        ) from exc

    name = ""
    title = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        heading = stripped.lstrip("#").strip()
        if not heading:
            continue
        if not name:
            name = heading
        elif heading.casefold() in _SECTION_HEADINGS:
            break  # a section heading, not a title
        elif not title:
            title = heading
            break
    if not name:
        for line in text.splitlines():
            if line.strip():
                name = line.strip()
                break

    skills, summary = _split_skills(text)
    return CandidateProfile(name=name, title=title, summary=summary, skills=skills)


def _split_skills(text: str) -> tuple[tuple[str, ...], str]:
    """Return ``(skills, rest)``: everything outside the Skills section."""
    match = _SKILLS_HEADING.search(text)
    if match is None:
        return (), text.strip()
    head = text[: match.start()]
    tail = text[match.end() :]
    # the section ends at the next markdown heading, if any
    end = re.search(r"^\s*#{1,6}\s+\S", tail, re.MULTILINE)
    section = tail[: end.start()] if end else tail
    rest = tail[end.start() :] if end else ""

    skills: list[str] = []
    for line in section.splitlines():
        bullet = _BULLET.match(line)
        if bullet:
            skills.append(bullet.group(1).strip())
        elif line.strip():
            skills.extend(part.strip() for part in line.split(",") if part.strip())
    return tuple(skills), (head + rest).strip()
