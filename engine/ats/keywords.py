"""Keyword matcher + gap analysis (task 9.3).

Extracts the keyword set a job description demands, matches it against the
resume, and reports *what the resume covers, what is missing and what to
do about it*. Matching is layered:

1. **exact** — case-folded string equality;
2. **stemmed** — a small, deterministic stemmer (trailing ``s`` / ``ing``
   / ``ed`` / ``tion`` handling) so ``optimizing`` matches ``optimize``;
3. **synonym** — the shipped :data:`SYNONYMS` table (PostgreSQL = Postgres,
   k8s = kubernetes, ML = machine learning …) so industry shorthand is not
   scored as a gap.

Hard gates stay in the job pipeline (2.8): the matcher *reports*, never
blocks.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

__all__ = [
    "SYNONYMS",
    "gap_report",
    "job_keywords",
    "keyword_coverage",
    "match_keywords",
    "normalise",
    "resume_keywords",
    "stem",
]

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+/#.-]*")
_KEEP_SHORT = frozenset({"c", "r", "go", "ai", "ml", "ux", "ui", "qa", "hr"})

#: canonical phrase → accepted aliases (both directions are matched). These
#: are *ATS shorthand facts*, not glossaries of the whole trade.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "postgres": ("postgresql", "psql"),
    "kubernetes": ("k8s", "kube"),
    "machine learning": ("ml",),
    "artificial intelligence": ("ai",),
    "javascript": ("js", "ecmascript", "es6"),
    "typescript": ("ts",),
    "continuous integration": ("ci",),
    "continuous delivery": ("cd",),
    "continuous deployment": ("cd",),
    "user experience": ("ux",),
    "user interface": ("ui",),
    "quality assurance": ("qa",),
    "search engine optimization": ("seo",),
    "amazon web services": ("aws",),
    "google cloud": ("gcp",),
    "microsoft azure": ("azure",),
    "natural language processing": ("nlp",),
    "computer vision": ("cv",),
    "application programming interface": ("api", "rest api"),
    "representational state transfer": ("rest",),
    "structured query language": ("sql",),
    "extract transform load": ("etl",),
    "customer relationship management": ("crm",),
    "enterprise resource planning": ("erp",),
}

#: filler tokens that are never keywords (kept small and documented).
STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "will",
        "are",
        "you",
        "your",
        "our",
        "have",
        "has",
        "had",
        "was",
        "were",
        "been",
        "job",
        "role",
        "team",
        "work",
        "join",
        "new",
        "all",
        "any",
        "can",
        "its",
        "per",
        "via",
        "etc",
        "plus",
        "year",
        "years",
        "including",
        "about",
        "into",
        "such",
        "than",
        "then",
        "they",
        "them",
        "their",
        "who",
        "whom",
        "which",
        "when",
        "where",
        "what",
        "how",
        "strong",
        "great",
        "good",
        "best",
        "top",
        "able",
        "day",
        "month",
        "looking",
        "seeking",
        "candidate",
        "ideal",
        "help",
        "across",
        "between",
        "both",
        "each",
        "other",
        "some",
        "more",
        "most",
        "must",
        "should",
        "would",
        "could",
        "may",
        "might",
        "within",
        "using",
        "used",
        "also",
        "one",
        "two",
        "first",
        "next",
        "over",
        "under",
        "while",
        "works",
        "working",
        "opportunity",
        "passion",
        "passionate",
        "drive",
        "driven",
        "love",
        "like",
        "make",
        "making",
        "take",
        "taking",
        "part",
        "eg",
        "ie",
    }
)


def normalise(text: str) -> str:
    """Case-fold, strip accents and collapse whitespace/punctuation."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9+/#.\s-]", " ", folded)


def stem(token: str) -> str:
    """Tiny deterministic stemmer for the keyword plane.

    Handles the plural/gerund/past forms ATS keywords actually appear in;
    technical tokens (``kubernetes``, ``postgres``) pass through untouched.
    """
    word = token.lower()
    if len(word) <= 4 or word in _KEEP_SHORT:
        return word
    for suffix in ("ization", "isation", "tion", "sion", "ment"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    if word.endswith("ies") and len(word) > 5:
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "xes", "sses")) and len(word) > 5:
        return word[:-2]  # sibilant + es → class(es), box(es), wish(es)
    if word.endswith("ing") and len(word) > 6:
        base = word[:-3]
        return base[:-1] if len(base) > 4 and base[-1] == base[-2] else base
    if word.endswith("ed") and len(word) > 5:
        base = word[:-2]
        return base[:-1] if len(base) > 4 and base[-1] == base[-2] else base
    if word.endswith("s") and not word.endswith("ss") and len(word) > 4:
        return word[:-1]  # trailing-s plural: databases → database
    return word


# ── Extraction ───────────────────────────────────────────────────────────


def _tokens(text: str) -> list[str]:
    cleaned = normalise(text)
    out: list[str] = []
    for raw in _TOKEN_RE.findall(cleaned):
        token = raw.strip(".-/#").lower()
        if not token or token in STOPWORDS or len(token) < 2:
            continue
        if token not in _KEEP_SHORT and len(token) == 2 and token.isalpha():
            continue
        out.append(token)
    return out


def _phrases(text: str) -> list[str]:
    """Multi-word phrases that are ATS keywords (frameworks, practices)."""
    cleaned = normalise(text)
    return [p for p in _PHRASE_KEYWORDS if p in cleaned]


_PHRASE_KEYWORDS: tuple[str, ...] = (
    "machine learning",
    "artificial intelligence",
    "continuous integration",
    "continuous delivery",
    "continuous deployment",
    "user experience",
    "user interface",
    "quality assurance",
    "search engine optimization",
    "amazon web services",
    "google cloud",
    "microsoft azure",
    "natural language processing",
    "computer vision",
    "application programming interface",
    "data analysis",
    "data science",
    "project management",
    "product management",
    "technical writing",
    "rest api",
    "node.js",
    "react.js",
    "vue.js",
)


def _alias_map() -> dict[str, str]:
    """Every known spelling → the canonical phrase it counts as."""
    mapping: dict[str, str] = {}
    for canonical, aliases in SYNONYMS.items():
        mapping[canonical] = canonical
        for alias in aliases:
            mapping[alias] = canonical
    return mapping


_ALIASES = _alias_map()


def job_keywords(description: str, *, title: str = "", min_len: int = 2) -> list[str]:
    """The keyword set a job description demands.

    Single tokens survive when they are long enough to be meaningful or are
    known industry shorthand; multi-word phrases are matched against the
    shipped phrase table. Output is de-duplicated and sorted so reports are
    stable across runs.
    """
    if min_len < 1:
        raise ValueError("min_len must be >= 1")
    tokens = [t for t in _tokens(description) if len(t) >= min_len or t in _KEEP_SHORT]
    return sorted(set(tokens) | set(_phrases(description)) | set(_tokens(title)))


def resume_keywords(resume: Any, *, min_len: int = 2) -> list[str]:
    """Every keyword-like token found anywhere in the parsed resume."""
    parts: list[str] = [getattr(resume, "raw_text", "") or ""]
    parts.extend(getattr(resume, "skills", []) or [])
    for entry in list(getattr(resume, "experience", []) or []):
        parts.append(str(entry.get("role", "")))
        parts.append(str(entry.get("org", "")))
        parts.extend(str(s) for s in entry.get("summary", []) or [])
    for entry in list(getattr(resume, "education", []) or []):
        parts.append(str(entry.get("degree", "")))
        parts.append(str(entry.get("school", "")))
    text = " ".join(parts)
    tokens = [t for t in _tokens(text) if len(t) >= min_len or t in _KEEP_SHORT]
    return sorted(set(tokens) | set(_phrases(text)))


# ── Matching ─────────────────────────────────────────────────────────────


def _canonical(token: str) -> str:
    """The spelling ``token`` counts as (alias folding + stemming)."""
    lowered = token.lower()
    if lowered in _ALIASES:
        return _ALIASES[lowered]
    return stem(lowered)


def match_keywords(
    required: list[str], present: list[str]
) -> tuple[list[str], list[str], dict[str, str]]:
    """Match ``required`` job keywords against the resume's keyword set.

    Returns ``(matched, missing, how)`` where ``how[keyword]`` is one of
    ``"exact"`` / ``"stem"`` / ``"synonym"``. Canonically equal keywords
    (``PostgreSQL`` vs ``postgres``, ``k8s`` vs ``kubernetes``) match even
    when the surface strings differ.
    """
    have = {_canonical(t) for t in present}
    have_raw = {t.lower() for t in present}
    matched: list[str] = []
    missing: list[str] = []
    how: dict[str, str] = {}
    for keyword in required:
        lowered = keyword.lower()
        if lowered in have_raw:
            matched.append(keyword)
            how[keyword] = "exact"
        elif _canonical(keyword) in have:
            matched.append(keyword)
            how[keyword] = "synonym" if lowered in _ALIASES or stem(lowered) != lowered else "stem"
        else:
            missing.append(keyword)
    return matched, missing, how


def keyword_coverage(required: list[str], matched: list[str]) -> float:
    """0-1 fraction of required keywords matched (1.0 when none required)."""
    if not required:
        return 1.0
    return round(len(matched) / len(required), 4)


def gap_report(
    required: list[str], matched: list[str], missing: list[str], how: dict[str, str]
) -> list[dict[str, str]]:
    """One improvement suggestion per missing keyword.

    The suggestions are honest about *placement*: a missing skill should be
    added to the Skills section only when the applicant genuinely holds it;
    the report says so explicitly rather than coaching fabrication.
    """
    suggestions: list[dict[str, str]] = []
    for keyword in missing:
        suggestions.append(
            {
                "category": "keyword_match",
                "priority": "high" if len(missing) <= 5 else "medium",
                "suggestion": (
                    f"Add '{keyword}' to the Skills section if (and only if) "
                    "you genuinely hold it, and mirror it once in a dated "
                    "experience bullet so the claim is evidenced."
                ),
            }
        )
    covered = {k: v for k, v in how.items() if v != "exact"}
    for keyword, method in sorted(covered.items()):
        suggestions.append(
            {
                "category": "keyword_match",
                "priority": "low",
                "suggestion": (
                    f"'{keyword}' is covered by {method} matching; spelling it "
                    "exactly as the posting does removes any parser doubt."
                ),
            }
        )
    return suggestions
