"""Pipeline orchestration.

Phase 2/3/9 pipelines are intentionally thin here: the wiring points exist
so callers and tests can import them, and each raises
``NotImplementedError`` naming the task that implements it. This keeps the
run history honest — a stub can never be mistaken for a finished pipeline.
"""

from __future__ import annotations


def run_job_pipeline(
    job_url: str,
    resume_path: str,
    country: str,
    visa_route: str | None = None,
) -> dict:
    """Fetch job -> verify sponsor -> filter fraud -> generate ATS resume.

    Implemented in task 2.8 (v3.0 spec, §5 Phase 2).
    """
    raise NotImplementedError("run_job_pipeline is implemented in task 2.8")


def run_scholarship_pipeline(
    scholarship_id: str,
    field: str,
    background_path: str,
    career_goal: str,
) -> dict:
    """Match scholarship -> generate SOP / research proposal.

    Implemented in task 3.6 (v3.0 spec, §5 Phase 3).
    """
    raise NotImplementedError("run_scholarship_pipeline is implemented in task 3.6")


def run_ats_scan(workspace_id: str, file_id: str, job_url: str) -> dict:
    """Upload -> parse -> score -> persist (v4.0, §21).

    Implemented in task 9.5.
    """
    raise NotImplementedError("run_ats_scan is implemented in task 9.5")


def run_cv_improvement(workspace_id: str, file_id: str) -> dict:
    """Parse CV -> LLM improvements (v4.0, §11).

    Implemented in task 10.2.
    """
    raise NotImplementedError("run_cv_improvement is implemented in task 10.2")


def run_cover_letter(workspace_id: str, resume_id: str, job_url: str) -> dict:
    """Generate a cover letter from a stored resume (v4.0, §12).

    Implemented in task 10.4.
    """
    raise NotImplementedError("run_cover_letter is implemented in task 10.4")
