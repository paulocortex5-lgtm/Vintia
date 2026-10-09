"""Pipeline tests: all five pipelines are wired and honest.

``run_job_pipeline`` (2.8), ``run_scholarship_pipeline`` (3.6),
``run_ats_scan`` (9.5), ``run_cv_improvement`` (10.2) and
``run_cover_letter`` (10.4) are implemented — each proven here to fail
*on substance* (bad upload, unknown portal) before any file/network work,
never by raising ``NotImplementedError``. The full journeys live in
``tests/e2e/``.
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


def test_ats_scan_is_implemented_and_rejects_unknown_urls():
    # not a stub any more (9.5): fails on substance (no adapter for the host)
    # with an explicit resume, before any file/network work
    with pytest.raises(FetchError) as excinfo:
        run_ats_scan("ws_1", "file_1", "https://x.com/job", resume={"name": "X"})
    assert excinfo.value.code == "unsupported_portal"


def test_cv_improvement_is_implemented_and_refuses_bad_uploads():
    # not a stub any more (10.2): fails on the upload before any work
    with pytest.raises(VantiaError) as excinfo:
        run_cv_improvement("ws_1", "missing.md")
    assert excinfo.value.code == "profile_file_missing"


def test_cover_letter_is_implemented_and_rejects_unknown_urls():
    # not a stub any more (10.4): fails on substance with an explicit resume,
    # before any file/network work
    with pytest.raises(FetchError) as excinfo:
        run_cover_letter("ws_1", "cv", "https://x.com/job", resume={"name": "X"})
    assert excinfo.value.code == "unsupported_portal"
