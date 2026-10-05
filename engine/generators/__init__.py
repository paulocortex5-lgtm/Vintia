"""Artifact generators (tasks 2.4-2.7).

Generators are the read-write half of the engine: they take a candidate
profile plus a :class:`~engine.sources.portals.base.JobListing` and emit
an artifact (resume, cover letter, SOP). The LLM is an *accelerator*, not
a dependency: every generator has a deterministic layer that runs with no
provider, no key and no network, and optionally calls
:mod:`engine.llm` to polish it.

Task 2.7 (:mod:`engine.generators.resume`) wires the security guardrails
from task 2.5/2.6 in: the untrusted job listing is injection-guarded and
fraud-scored before use, and PII is redacted out of anything that reaches
a prompt.
"""

from __future__ import annotations

from .resume import (
    CandidateProfile,
    Education,
    Experience,
    ResumeArtifact,
    generate_resume,
)

__all__ = [
    "CandidateProfile",
    "Education",
    "Experience",
    "ResumeArtifact",
    "generate_resume",
]
