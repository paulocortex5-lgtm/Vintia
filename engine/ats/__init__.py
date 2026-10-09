"""ATS scoring engine (Phase 9).

Extracts a resume into a structured :class:`~engine.ats.parser.ParsedResume`
(9.1), scores it against a target job with the twelve-point rubric (9.2),
and matches job keywords to resume keywords with a gap report (9.3).

Like every other engine half, this is deterministic first: it runs with no
provider, no key and no network, and the LLM only *polishes* the output when
explicitly supplied.
"""

from __future__ import annotations

from .keywords import job_keywords, keyword_coverage, match_keywords
from .parser import ParsedResume, parse_resume
from .scoring import CATEGORY_WEIGHTS, score_resume

__all__ = [
    "CATEGORY_WEIGHTS",
    "ParsedResume",
    "job_keywords",
    "keyword_coverage",
    "match_keywords",
    "parse_resume",
    "score_resume",
]
