"""Resume parser (task 9.1).

Turns an uploaded resume into a structured :class:`ParsedResume` so the ATS
scoring engine (9.2) and keyword matcher (9.3) never re-read raw bytes.

Formats
-------
* **JSON** — an explicit profile document (the precise path; unknown keys
  ignored, ``skills`` may be strings or ``{"name": ...}`` objects). Highest
  extraction confidence.
* **PDF** — text pulled by ``pypdf`` from the ``ats`` extra. When the
  extractor is missing the parser refuses loudly
  (``resume_extractor_unavailable``) instead of scoring an empty resume.
* **DOCX** — paragraph text pulled by ``python-docx``; same loud rule.
* **markdown / plain text** — heuristic section split (Skills / Education /
  Experience) plus regex contact capture.

Extraction confidence is *reported*, never assumed: ``high`` when every
field came from an explicit structure or a clearly delimited section,
``partial`` when the body was read but boundaries were inferred, ``low``
when contact details could not be located at all.
"""

from __future__ import annotations

import io
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from ..errors import VantiaError

__all__ = [
    "PARSER_VERSION",
    "ParsedResume",
    "PdfExtractor",
    "detect_format",
    "extract_docx",
    "extract_pdf",
    "parse_resume",
]

PARSER_VERSION = "1.0"


@dataclass
class ParsedResume:
    """A resume as structured facts plus honest extraction metadata."""

    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    website: str = ""
    summary: str = ""
    skills: list[str] = field(default_factory=list)
    experience: list[dict[str, Any]] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    raw_text: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    parser_version: str = PARSER_VERSION
    extraction_confidence: str = "partial"  # high | partial | low
    file_size_bytes: int = 0
    source_format: str = ""
    parse_warnings: list[str] = field(default_factory=list)

    # ── Serialisation ────────────────────────────────────────────────
    @property
    def metadata(self) -> dict[str, Any]:
        """The ``parser_metadata`` block expected by ats_score.schema.json."""
        return {
            "parser_version": self.parser_version,
            "extraction_confidence": self.extraction_confidence,
            "file_size_bytes": self.file_size_bytes,
            "source_format": self.source_format,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "website": self.website,
            "summary": self.summary,
            "skills": list(self.skills),
            "experience": [dict(e) for e in self.experience],
            "education": [dict(e) for e in self.education],
            "languages": list(self.languages),
            "certifications": list(self.certifications),
            "sections": dict(self.sections),
            "metadata": self.metadata,
            "parse_warnings": list(self.parse_warnings),
        }

    # ── Derived facts ────────────────────────────────────────────────
    @property
    def years_experience(self) -> float:
        """Total span of dated experience entries, in years.

        Only *dated* entries count: a resume that never states dates gets
        ``0.0`` rather than a guess (9.2 reports the gap instead).
        """
        total = 0.0
        for entry in self.experience:
            start = _span_month(str(entry.get("start", "")))
            end = _span_month(str(entry.get("end", "")))
            if start is None or end is None:
                continue
            total += max(0.0, round((end - start).days / 365.25, 3))
        return round(total, 3)

    @property
    def has_dates(self) -> bool:
        return any(entry.get("start") or entry.get("end") for entry in self.experience)


def _month_start(iso: str | None) -> date | None:
    """Legacy shim kept for internal consistency — use :func:`_span_month`."""
    return _span_month(iso or "")


# ── Contact capture + section splitting ────────────────────────────────

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{2,4}[\s.-]?\d{2,4}(?!\d)"
)
_WEBSITE_RE = re.compile(
    r"(?:(?:https?://|www\.)[^\s,;]+|[A-Za-z0-9-]+\.(?:com|io|dev|me|co|ai)\b)",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(
    r"^\s*(?:location|based\s+in)\s*[:\-]?\s*(.+)$", re.IGNORECASE | re.MULTILINE
)
_HEADING_RE = re.compile(r"^\s*#{0,6}\s*([A-Za-z][A-Za-z /&-]{1,32})\s*#*\s*$")
_BULLET_RE = re.compile(r"^\s*(?:[-*•▪]|\d+\.)\s+(.*)$")

#: heading → canonical section key
_SECTION_KEYS: dict[str, str] = {
    "skills": "skills",
    "technical skills": "skills",
    "core competencies": "skills",
    "education": "education",
    "academic background": "education",
    "experience": "experience",
    "employment": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment history": "experience",
    "projects": "projects",
    "summary": "summary",
    "professional summary": "summary",
    "profile": "summary",
    "objective": "summary",
    "contact": "contact",
    "contact information": "contact",
    "languages": "languages",
    "certifications": "certifications",
    "certificates": "certifications",
    "awards": "awards",
    "references": "references",
}


def _pick(text: str, regex: re.Pattern[str]) -> str:
    """First capture group of ``regex`` in ``text``; ``''`` when absent."""
    match = regex.search(text)
    if match is None:
        return ""
    value = (match.group(1) if match.groups() else match.group(0)).strip()
    return value.strip(" ,.;")


def _split_sections(text: str) -> tuple[dict[str, str], str]:
    """Split ``text`` into ``{section_key: body}`` plus the unsectioned head."""
    sections: dict[str, str] = {}
    head: list[str] = []
    current: str | None = None
    for line in text.splitlines():
        heading = _HEADING_RE.match(line)
        if heading:
            key = _SECTION_KEYS.get(heading.group(1).strip().casefold())
            if key:
                current = key
                sections.setdefault(key, "")
                continue
        if current is None:
            head.append(line)
        else:
            sections[current] += line + "\n"
    return (
        {k: v.strip() for k, v in sections.items() if v.strip()},
        "\n".join(head).strip(),
    )


# ── List + entry parsing ───────────────────────────────────────────────


def _parse_list(body: str) -> list[str]:
    """A Skills/Languages body → a de-duplicated list of strings."""
    out: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        bullet = _BULLET_RE.match(line)
        text = (bullet.group(1) if bullet else stripped).strip(" ;")
        for part in re.split(r"[,|]", text):
            part = part.strip(" ;")
            if part and len(part) <= 60 and part not in out:
                out.append(part)
    return out


_MONTHS: dict[str, int] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_PRESENT_TOKENS = frozenset({"present", "current", "ongoing", "now"})

_MONTH_YEAR_RE = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s*(\d{4})",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _when_date(text: str) -> str:
    """Normalise date-ish text to ``YYYY-MM`` / ``YYYY`` / ``present``.

    Anything unrecognised returns ``""`` — the entry keeps its role/org but
    contributes no span to :attr:`ParsedResume.years_experience`.
    """
    token = text.strip().rstrip(".,").lower()
    if token in _PRESENT_TOKENS:
        return "present"
    match = _MONTH_YEAR_RE.search(token)
    if match:
        stem = match.group(1).lower()
        month = 9 if stem.startswith("sept") else _MONTHS[stem[:3]]
        return f"{match.group(2)}-{month:02d}"
    year = _YEAR_RE.search(token)
    if year:
        return year.group(0)
    return ""


def _span_month(iso_like: str) -> date | None:
    """``YYYY-MM`` / ``YYYY`` / ``present`` → month-start date for span maths."""
    token = (iso_like or "").strip().lower()
    if token in _PRESENT_TOKENS:
        today = datetime.now(UTC).date()
        return date(today.year, today.month, 1)
    month_year = re.fullmatch(r"(\d{4})-(\d{2})", token)
    if month_year:
        try:
            return date(int(month_year.group(1)), int(month_year.group(2)), 1)
        except ValueError:
            return None
    if re.fullmatch(r"\d{4}", token):
        return date(int(token), 1, 1)
    return None


def _split_entry_line(line: str) -> tuple[str, str, str, str]:
    """``Role, Org (Jan 2022 - Present)`` → ``(role, org, start, end)``."""
    spans = re.findall(r"[([]([^()[\]]*\d{4}[^()[\]]*|present|current)[)\]]", line, re.IGNORECASE)
    cleaned = line
    for span in spans:
        cleaned = cleaned.replace(f"({span})", " ").replace(f"[{span}]", " ")
    cleaned = re.sub(r"[(){}\[\]]", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;")
    start = ""
    end = ""
    if spans:
        chunk = spans[0]
        for token in (" - ", " – ", " — ", " to "):
            chunk = chunk.replace(token, "|")
        bits = [b.strip() for b in chunk.split("|") if b.strip()]
        if bits:
            start = _when_date(bits[0])
            end = _when_date(bits[-1])
    pieces = [p.strip() for p in re.split(r",|@", cleaned, maxsplit=1) if p.strip()]
    if len(pieces) >= 2:
        return pieces[0], pieces[1], start, end
    return cleaned, "", start, end


def _parse_entries(body: str) -> list[dict[str, Any]]:
    """Experience/education body → structured entries.

    A heading line (non-bullet) opens a new entry; bullets under it become
    ``summary`` lines. Undated headings still produce an entry — the
    scoring engine reports the missing dates, never guesses them.
    """
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in body.splitlines():
        if not line.strip():
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            if current is not None:
                current.setdefault("summary", []).append(bullet.group(1).strip())
            continue
        title, org, start, end = _split_entry_line(line.strip())
        if not title:
            continue
        current = {"role": title, "org": org, "start": start, "end": end, "summary": []}
        entries.append(current)
    return entries


def _education_from_text(body: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in body.splitlines():
        stripped = line.strip(" ;")
        if not stripped:
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            stripped = bullet.group(1).strip(" ;")
        out.append({"degree": stripped, "school": "", "year": ""})
    return out


# ── JSON builder (the precise parsing path) ────────────────────────────


def build_from_json(data: dict[str, Any], *, file_size_bytes: int = 0) -> ParsedResume:
    """Build from an explicit profile document — highest confidence."""
    resume = ParsedResume(
        name=str(data.get("name", "")),
        title=str(data.get("title", "")),
        email=str(data.get("email", "")),
        phone=str(data.get("phone", "")),
        location=str(data.get("location", "")),
        website=str(data.get("website") or data.get("linkedin", "")),
        summary=str(data.get("summary", "")),
        skills=_strings(data.get("skills")),
        experience=_entries_from_json(data.get("experience")),
        education=_education_from_json(data.get("education")),
        languages=_strings(data.get("languages")),
        certifications=_strings(data.get("certifications")),
        raw_text=str(data.get("summary", "")),
        parser_version=PARSER_VERSION,
        extraction_confidence="high",
        file_size_bytes=file_size_bytes,
        source_format="json",
    )
    resume.sections = {"summary": resume.summary, "skills": ", ".join(resume.skills)}
    if not resume.name:
        resume.parse_warnings.append("no name field in the JSON profile")
    return resume


# ── JSON helpers ─────────────────────────────────────────────────────────


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    out: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                out.append(str(item["name"]).strip())
    return out


def _entries_from_json(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            out.append({"role": item, "org": "", "start": "", "end": "", "summary": []})
        elif isinstance(item, dict):
            summaries = item.get("summary") or ()
            if isinstance(summaries, str):
                summaries = (summaries,)
            out.append(
                {
                    "role": str(item.get("role", item.get("title", ""))),
                    "org": str(item.get("org", item.get("company", ""))),
                    "start": str(item.get("start", "")),
                    "end": str(item.get("end", "")),
                    "summary": [str(s) for s in summaries],
                }
            )
    return out


def _education_from_json(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            out.append({"degree": item, "school": "", "year": ""})
        elif isinstance(item, dict):
            out.append(
                {
                    "degree": str(item.get("degree", "")),
                    "school": str(item.get("school", "")),
                    "year": str(item.get("year", "")),
                }
            )
    return out


# ── Text builder (heuristic markdown / plain-text parsing) ───────────────


def build_from_text(text: str, *, source_format: str, file_size_bytes: int = 0) -> ParsedResume:
    """Heuristic parse of markdown / plain-text resume bodies."""
    if not text.strip():
        raise VantiaError("empty resume text", code="resume_parse_error")
    sections, head = _split_sections(text)

    name = ""
    title = ""
    for line in head.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("-", "*", "•")):
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        if not name:
            name = stripped
        elif not title:
            title = stripped
            break

    email = _pick(text, _EMAIL_RE)
    resume = ParsedResume(
        name=name,
        title=title,
        email=email,
        phone=_pick(text, _PHONE_RE),
        location=_pick(text, _LOCATION_RE),
        website=_pick(text, _WEBSITE_RE),
        summary=sections.get("summary", "").strip(),
        skills=_parse_list(sections.get("skills", "")),
        experience=_parse_entries(sections.get("experience", "")),
        languages=_parse_list(sections.get("languages", "")),
        certifications=_parse_list(sections.get("certifications", "")),
        raw_text=text,
        sections=sections,
        parser_version=PARSER_VERSION,
        extraction_confidence="partial",
        file_size_bytes=file_size_bytes,
        source_format=source_format,
    )
    edu_body = sections.get("education", "")
    resume.education = _education_from_text(edu_body) if edu_body else []
    if not email:
        resume.extraction_confidence = "low"
        resume.parse_warnings.append("no email address found in the resume")
    if not resume.location:
        resume.parse_warnings.append("no location line found (Location: …)")
    return resume


# ── Binary extraction (installed via `pip install -e ".[ats]"`) ────────

PdfExtractor = Callable[[bytes], str]


def _default_pdf_extractor() -> PdfExtractor:
    from pypdf import PdfReader  # type: ignore[import-untyped]

    def _extract(data: bytes) -> str:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    return _extract


def _default_docx_extractor() -> PdfExtractor:
    import docx  # type: ignore[import-untyped]

    def _extract(data: bytes) -> str:
        document = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs if p.text.strip())

    return _extract


def extract_pdf(data: bytes, *, extractor: PdfExtractor | None = None) -> str:
    """PDF bytes → text; refuses loudly when no extractor is installed."""
    try:
        fn = extractor if extractor is not None else _default_pdf_extractor()
        text = fn(data)
    except ModuleNotFoundError as exc:
        raise VantiaError(
            f"PDF extractor unavailable ({exc.name}); install the `ats` extra "
            "(pip install -e '.[ats]') to score PDF resumes",
            code="resume_extractor_unavailable",
            format="pdf",
        ) from exc
    except Exception as exc:
        raise VantiaError(
            f"could not extract text from the PDF: {exc}",
            code="resume_parse_error",
            format="pdf",
        ) from exc
    if not text.strip():
        raise VantiaError("PDF contained no extractable text", code="resume_parse_error")
    return text.strip()


def extract_docx(data: bytes, *, extractor: PdfExtractor | None = None) -> str:
    """DOCX bytes → paragraph text; same loud-refusal rule as PDF."""
    try:
        fn = extractor if extractor is not None else _default_docx_extractor()
        text = fn(data)
    except ModuleNotFoundError as exc:
        raise VantiaError(
            f"DOCX extractor unavailable ({exc.name}); install the `ats` extra "
            "(pip install -e '.[ats]') to score DOCX resumes",
            code="resume_extractor_unavailable",
            format="docx",
        ) from exc
    except Exception as exc:
        raise VantiaError(
            f"could not extract text from the DOCX: {exc}",
            code="resume_parse_error",
            format="docx",
        ) from exc
    if not text.strip():
        raise VantiaError("DOCX contained no extractable text", code="resume_parse_error")
    return text.strip()


# ── Public entry point ────────────────────────────────────────────────

_MAGIC: tuple[tuple[bytes, str], ...] = ((b"%PDF", "pdf"), (b"PK\x03\x04", "docx"))


def detect_format(data: bytes, *, hint: str = "") -> str:
    """Best-effort format detection for uploaded bytes.

    ``hint`` may be a filename (``resume.md``), a bare extension
    (``markdown``) or a MIME tail (``application/json``) — uploads arrive
    with a ``Content-Type``, not a filename.
    """
    raw = (hint or "").split(";")[0].strip().lower()
    ext = os.path.splitext(raw)[1].lstrip(".")
    if not ext and "/" in raw:
        ext = raw.rsplit("/", 1)[-1]
    elif not ext:
        ext = raw
    if ext in {"pdf", "docx", "json", "md", "txt", "markdown"}:
        return "md" if ext == "markdown" else ext
    for magic, name in _MAGIC:
        if data.startswith(magic):
            return name
    return "txt"


def _text_format(fmt: str) -> str:
    return "md" if fmt == "markdown" else fmt


def parse_resume(
    source: str | bytes | dict[str, Any],
    *,
    content_type: str = "",
    pdf_extractor: PdfExtractor | None = None,
    docx_extractor: PdfExtractor | None = None,
) -> ParsedResume:
    """Parse an uploaded resume into a :class:`ParsedResume`.

    ``source`` is a file path, a buffer of uploaded bytes (``content_type``
    hints at the extension) or an already-decoded JSON profile dict.
    Raises :class:`VantiaError` with a stable ``code`` on anything that
    cannot be honestly parsed — an empty resume scored as 0/100 is worse
    than a clear error.
    """
    if isinstance(source, dict):
        return build_from_json(source, file_size_bytes=len(json.dumps(source).encode("utf-8")))

    if isinstance(source, bytes):
        data = source
        hint = content_type.split("/")[-1].split(";")[0]
    else:
        if not os.path.exists(source):
            raise VantiaError(
                f"resume file not found: {source}", code="profile_file_missing", path=source
            )
        with open(source, "rb") as fh:
            data = fh.read()
        hint = source

    size = len(data)
    fmt = _text_format(detect_format(data, hint=hint))
    if fmt == "json":
        try:
            return build_from_json(json.loads(data.decode("utf-8")), file_size_bytes=size)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise VantiaError(f"invalid JSON resume: {exc}", code="profile_parse_error") from exc
    if fmt == "pdf":
        text = extract_pdf(data, extractor=pdf_extractor)
        return build_from_text(text, source_format="pdf", file_size_bytes=size)
    if fmt == "docx":
        text = extract_docx(data, extractor=docx_extractor)
        return build_from_text(text, source_format="docx", file_size_bytes=size)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VantiaError(
            "resume is neither text nor a known binary format (.json/.pdf/.docx/.md/.txt only)",
            code="profile_format_unsupported",
        ) from exc
    return build_from_text(text, source_format=fmt, file_size_bytes=size)
