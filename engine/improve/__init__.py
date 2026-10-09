"""CV improvement package (task 10.2) — targeted rewriting, facts preserved.

The engine takes a :class:`~engine.ats.parser.ParsedResume` and emits a
schema-valid ``cv_improvement`` payload: a reviewable list of edits plus the
full improved CV. Deterministic first (repo pattern); the shipped
``v1_cv_improve.md`` prompt is the optional accelerator.
"""

from __future__ import annotations

from .cv import ImproveArtifact, improve_cv

__all__ = ["ImproveArtifact", "improve_cv"]
