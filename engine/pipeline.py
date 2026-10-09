"""Pipeline orchestration.

``run_job_pipeline`` (task 2.8) is the first fully wired pipeline:

    fetch → active-only screen → fraud screen (2.5) → sponsor-register
    badge (2.3) → ATS resume generation (2.7)

Guardrail policy: fraud *screens* (``clean``/``review`` pass through
with the report attached; ``block`` raises), registers *tag* (never
drop), closed listings are refused (``listing_inactive``). The LLM is
an accelerator — pass ``client``/``chain`` to polish the resume, or
leave them ``None`` for the deterministic ship path.

The remaining pipelines still raise ``NotImplementedError`` naming the
task that implements them, so a stub can never be mistaken for finished
work.
"""

from __future__ import annotations

import os
from dataclasses import asdict
from datetime import date

from .ats import parse_resume, score_resume
from .errors import FetchError, RegisterPending, VantiaError
from .generators import generate_proposal, generate_resume, generate_sop, load_profile
from .json_utils import atomic_write_json, load_json, validate
from .llm import LLMClient
from .scholarships import get_scholarship, map_credential, window_status
from .security import fraud
from .sources import Fetcher, badge, fetch_register, filter_active, load_listing, register_spec
from .sources.portals.base import JobListing

__all__ = [
    "run_ats_scan",
    "run_cover_letter",
    "run_cv_improvement",
    "run_job_pipeline",
    "run_scholarship_pipeline",
]


def _sponsorship(
    listing: JobListing, country: str, fetcher: Fetcher
) -> tuple[JobListing, dict[str, object]]:
    """Badge ``listing`` against ``country``'s register; never fatal.

    Pending / unavailable registers degrade to the text tagger with the
    reason recorded — badging is a tag, not a gate (session 7 policy).
    """
    info: dict[str, object] = {
        "country": country,
        "register_status": "",
        "matched": None,
        "register_size": None,
        "error": None,
    }
    try:
        spec = register_spec(country)
    except FetchError as exc:  # unknown country: badge with text only
        info["register_status"] = "unknown_country"
        info["error"] = str(exc)
        return badge(listing), info

    info["register_status"] = spec.status
    try:
        register = fetch_register(country, fetcher)
    except RegisterPending as exc:
        info["error"] = str(exc)
        return badge(listing), info
    except FetchError as exc:
        info["register_status"] = "unavailable"
        info["error"] = str(exc)
        return badge(listing), info

    info["register_size"] = len(register)
    info["matched"] = register.matches(listing.company)
    return badge(listing, register), info


def run_job_pipeline(
    job_url: str,
    resume_path: str,
    country: str,
    visa_route: str | None = None,
    *,
    fetcher: Fetcher | None = None,
    client: LLMClient | None = None,
    chain: list | None = None,
    run_id: str = "0",
) -> dict:
    """Fetch job → verify sponsor → filter fraud → generate ATS resume.

    ``country`` selects the sponsor register to badge against (ISO
    3166-1 alpha-2, e.g. ``"GB"``); ``resume_path`` is a ``.json`` or
    ``.md``/``.txt`` profile read by
    :func:`engine.generators.profile.load_profile`.

    Raises ``FetchError`` (``listing_inactive`` /
    ``unsupported_portal`` / robots), ``FraudSignalError`` (block
    verdict) or ``InjectionDetectedError`` (hostile posting text).

    Scope note: loading by URL covers the W/G/L portals (2.2);
    government sources are harvested through their adapters and are not
    yet addressable by direct URL (carried follow-up).
    """
    http = fetcher if fetcher is not None else Fetcher()
    listing = load_listing(job_url, http)  # robots + rate limit + closed-refusal inside
    if not filter_active([listing]):  # belt & braces — active-only policy (2.1)
        raise FetchError(
            f"listing is no longer active: {job_url}",
            code="listing_inactive",
            url=job_url,
            closes_at=listing.closes_at,
        )

    report = fraud.assess(listing)  # screen: clean/review pass, block raises
    if report.blocked:
        fraud.block(listing)

    listing, sponsorship = _sponsorship(listing, country, http)
    candidate = load_profile(resume_path)
    artifact = generate_resume(candidate, listing, client=client, chain=chain, run_id=run_id)

    return {
        "pipeline": {
            "task": "2.8",
            "job_url": job_url,
            "country": country,
            "visa_route": visa_route,
            "run_id": run_id,
        },
        "job": asdict(listing),
        "fraud": report.to_dict(),
        "sponsorship": sponsorship,
        "resume": artifact.to_dict(),
    }


def run_scholarship_pipeline(
    scholarship_id: str,
    field: str,
    background_path: str,
    career_goal: str,
    *,
    research_interests: str = "",
    target_program: str = "",
    applicant_id: str = "",
    degree_level: str = "MSc",
    country: str | None = None,
    today: date | None = None,
    client: LLMClient | None = None,
    chain: list | None = None,
    run_id: str = "0",
) -> dict:
    """Match scholarship → credential check → window → SOP + research proposal.

    Order of operations (task 3.6): resolve the program in the database
    (3.1), load the applicant's background, compare their latest
    education entry's equivalence to the entry level (3.4 — a
    three-valued, informational verdict that never blocks the run),
    record the application window against ``today`` (3.5 — also
    informational), then generate both artifacts (3.2 / 3.3).

    Raises ``scholarship_not_found``, ``profile_*`` errors,
    ``proposal_keywords_insufficient`` and ``SchemaValidationError``.
    The window status never gates generation: an application prepared
    before the cycle opens is still useful.
    """
    sch = get_scholarship(scholarship_id)
    candidate = load_profile(background_path)

    if candidate.education:
        credential = map_credential(scholarship_id, candidate.education[0].degree, country=country)
    else:
        credential = {
            "scholarship": {
                "id": sch.id,
                "name": sch.name,
                "level": sch.level,
                "min_eqf_level": sch.min_eqf_level,
                "url": sch.url,
            },
            "credential_query": "",
            "issuing_country": country.upper() if country else None,
            "credential": None,
            "meets_level": None,
            "required_eqf_level": sch.min_eqf_level,
            "advice": (
                "no education entry in the profile — add one to check the "
                "programme's entry-level equivalence"
            ),
        }

    window = window_status(sch, today)
    sop = generate_sop(
        candidate,
        scholarship=sch,
        field_of_study=field,
        career_goal=career_goal,
        target_program=target_program,
        applicant_id=applicant_id,
        client=client,
        chain=chain,
        run_id=run_id,
    )
    proposal = generate_proposal(
        candidate,
        field_of_study=field,
        research_interests=research_interests or career_goal,
        career_goal=career_goal,
        target_program=target_program,
        funding_body=sch.provider,
        applicant_id=applicant_id,
        degree_level=degree_level,
        client=client,
        chain=chain,
        run_id=run_id,
    )

    return {
        "pipeline": {
            "task": "3.6",
            "scholarship_id": scholarship_id,
            "field": field,
            "run_id": run_id,
        },
        "scholarship": sch.to_dict(),
        "credential": credential,
        "window": window,
        "sop": sop.to_dict(),
        "proposal": proposal.to_dict(),
    }


def run_ats_scan(
    workspace_id: str,
    file_id: str,
    job_url: str,
    *,
    resume: str | bytes | dict | None = None,
    fetcher: Fetcher | None = None,
    store_dir: str | None = None,
    run_id: str = "0",
) -> dict:
    """Upload -> parse -> score -> persist (v4.0, §21, task 9.5).

    Resume resolution: the explicit ``resume`` argument (profile dict /
    bytes / path) wins; otherwise the stored upload
    ``<store>/<workspace_id>/<file_id>`` where ``store`` is ``store_dir``
    or ``$VANTIA_WORKSPACE_DIR`` or ``workspace/``. The upload is read and
    parsed **before any network call**, a workspace id may not escape the
    store root (``..`` / absolute paths are refused), and an unparseable
    upload raises instead of being scored as an empty resume (9.1 rules).

    The posting is loaded through the standard loader (robots + rate limit
    + closed-refusal, 2.1/2.8) and scored deterministically (9.2) — no LLM,
    no key, no network beyond the posting itself. The report validates
    against ``ats_score.schema.json`` before it is returned and is
    persisted next to the upload as ``<file>.ats.json`` when a store file
    was used. Fraud/injection screens stay in the job pipeline (2.8); a
    scan never applies, it only reports.
    """
    report_path: str | None = None
    if resume is None:
        root = os.path.abspath(store_dir or os.environ.get("VANTIA_WORKSPACE_DIR", "workspace"))
        target = os.path.abspath(os.path.join(root, workspace_id, file_id))
        if not target.startswith(root + os.sep):
            raise VantiaError(
                "workspace path escapes the store root",
                code="workspace_path_invalid",
                workspace_id=workspace_id,
                file_id=file_id,
            )
        if not os.path.isfile(target):
            raise VantiaError(
                f"resume not found for {workspace_id}/{file_id}",
                code="profile_file_missing",
                workspace_id=workspace_id,
                file_id=file_id,
            )
        resume = target
        report_path = target + ".ats.json"

    parsed = parse_resume(resume)
    listing = load_listing(job_url, fetcher)
    if not listing.is_active():
        raise FetchError(
            f"listing is no longer active: {job_url}",
            code="listing_inactive",
            url=job_url,
            closes_at=listing.closes_at,
        )
    report = score_resume(
        parsed,
        job_title=listing.title,
        job_description=listing.description,
        job_location=listing.location,
    )
    payload = report.payload(resume_id=file_id, job_id=listing.external_id or job_url)
    schema = load_json(os.path.join(os.path.dirname(__file__), "schemas", "ats_score.schema.json"))
    if schema is None:  # pragma: no cover — packaged file must exist
        raise VantiaError("ats_score.schema.json missing", code="schema_missing")
    validate(payload, schema)
    if report_path is not None:
        atomic_write_json(report_path, payload)
    return {
        "pipeline": {
            "task": "9.5",
            "workspace_id": workspace_id,
            "file_id": file_id,
            "job_url": job_url,
            "run_id": run_id,
        },
        "job": asdict(listing),
        "report": payload,
        "report_path": report_path,
        "parser": {**parsed.metadata, "warnings": list(parsed.parse_warnings)},
    }


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
