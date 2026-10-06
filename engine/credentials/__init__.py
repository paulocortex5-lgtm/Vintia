"""Credential equivalence (task 2.4).

NVQ / HND / BTS / CAP / degree cycles ↔ EQF / ECTS, plus GPA → ECTS
grade conversion. Deterministic static registry by default; optional
owner-configured remote lookup via :func:`remote_lookup`.
"""

from __future__ import annotations

from .equivalence import (
    CREDENTIALS,
    ECTS_GRADES,
    Credential,
    EctsGrade,
    degree_in_country,
    describe,
    equivalence,
    gpa_to_ects,
    lookup,
    remote_lookup,
)

__all__ = [
    "CREDENTIALS",
    "ECTS_GRADES",
    "Credential",
    "EctsGrade",
    "degree_in_country",
    "describe",
    "equivalence",
    "gpa_to_ects",
    "lookup",
    "remote_lookup",
]
