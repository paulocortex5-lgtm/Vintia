"""Pipeline-stub tests: every pipeline is an honest, task-named NotImplementedError.

These stubs exist so callers/tests can import the wiring points; each one
names the task that implements it. We lock that contract down so a stub can
never be silently mistaken for finished work.
"""

import pytest

from engine.pipeline import (
    run_ats_scan,
    run_cover_letter,
    run_cv_improvement,
    run_job_pipeline,
    run_scholarship_pipeline,
)


def test_job_pipeline_is_a_task_2_8_stub():
    with pytest.raises(NotImplementedError, match="task 2.8"):
        run_job_pipeline("https://x.com/job", "cv.pdf", "CA")


def test_scholarship_pipeline_is_a_task_3_6_stub():
    with pytest.raises(NotImplementedError, match="task 3.6"):
        run_scholarship_pipeline("sch_1", "engineering", "background.pdf", "career")


def test_ats_scan_is_a_task_9_5_stub():
    with pytest.raises(NotImplementedError, match="task 9.5"):
        run_ats_scan("ws_1", "file_1", "https://x.com/job")


def test_cv_improvement_is_a_task_10_2_stub():
    with pytest.raises(NotImplementedError, match="task 10.2"):
        run_cv_improvement("ws_1", "file_1")


def test_cover_letter_is_a_task_10_4_stub():
    with pytest.raises(NotImplementedError, match="task 10.4"):
        run_cover_letter("ws_1", "resume_1", "https://x.com/job")
