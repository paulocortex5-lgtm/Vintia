"""Pipeline tests: the implemented job pipeline + the honest stubs.

``run_job_pipeline`` (2.8) is wired end to end; the remaining pipelines
still raise ``NotImplementedError`` naming the task that implements it,
so a stub can never be mistaken for finished work. The full journey
(fraud, registers, profiles, robots) lives in
``tests/e2e/test_job_pipeline.py``.
"""

import pytest

from engine.errors import FetchError, VantiaError
from engine.pipeline import (
    run_ats_scan,
    run_cover_letter,
    run_cv_improvement,
    run_job_pipeline,
    run_scholarship_pipeline,
)


def test_job_pipeline_is_implemented_and_rejects_unknown_urls():
    # not a stub any more: it fails on substance (no adapter for the host),
    # and the failure happens before any network I/O
    with pytest.raises(FetchError) as excinfo:
        run_job_pipeline("https://example.com/jobs/1", "cv.json", "CA")
    assert excinfo.value.code == "unsupported_portal"


def test_scholarship_pipeline_is_implemented_and_rejects_unknown_programs():
    # not a stub any more: it fails on substance before any file/network work
    with pytest.raises(VantiaError) as excinfo:
        run_scholarship_pipeline("nope", "ml", "absent.json", "goal")
    assert excinfo.value.code == "scholarship_not_found"


def test_ats_scan_is_a_task_9_5_stub():
    with pytest.raises(NotImplementedError, match="task 9.5"):
        run_ats_scan("ws_1", "file_1", "https://x.com/job")


def test_cv_improvement_is_a_task_10_2_stub():
    with pytest.raises(NotImplementedError, match="task 10.2"):
        run_cv_improvement("ws_1", "file_1")


def test_cover_letter_is_a_task_10_4_stub():
    with pytest.raises(NotImplementedError, match="task 10.4"):
        run_cover_letter("ws_1", "resume_1", "https://x.com/job")
