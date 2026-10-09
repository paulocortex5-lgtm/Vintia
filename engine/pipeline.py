"""Pipeline orchestration.

``run_job_pipeline`` (task 2.8) is the first fully wired pipeline:

    fetch → active-only screen → fraud screen (2.5) → sponsor-register
    badge (2.3) → ATS resume generation (2.7)

Guardrail policy: fraud *screens* (``clean``/``review`` pass through
with the report attached; ``block`` raises), registers *tag* (never
drop), closed listings are refused (``listing_inactive``). The LLM is
an accelerator — pass ``client``/``chain`` to polish the resume, or
leave them ``None`` for the deterministic ship path.

The five pipelines are now all wired: ``run_job_pipeline`` (2.8),
``run_scholarship_pipeline`` (3.6), ``run_ats_scan`` (9.5),
``run_cv_improvement`` (10.2) and ``run_cover_letter`` (10.4) — each one
deterministic-first, schema-valid on every path, and honest about what it
does not know. The three priced product runs (9.5 / 10.2 / 10.4)
additionally accept ``user_id`` for credit metering (task 11.4):
pre-flight (allowance + R46) before any work, charge on completion only,
and the charge is reported in the result's ``credits`` field.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict
from datetime import date

from .ats import parse_resume, score_resume
from .credits import CreditMeter, default_meter
from .errors import FetchError, RegisterPending, VantiaError
from .generators import (
    generate_cover_letter,
    generate_proposal,
    generate_resume,
    generate_sop,
    load_profile,
)
from .improve import improve_cv
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


def _resolve_upload(
    workspace_id: str,
    file_id: str,
    resume: str | bytes | dict | None,
    store_dir: str | None,
) -> tuple[str | bytes | dict, str | None]:
    """Resolve the upload for the 10.x/9.x pipelines.

    The explicit ``resume`` argument (profile dict / bytes / path) wins;
    otherwise the stored upload ``<store>/<workspace_id>/<file_id>`` where
    ``store`` is ``store_dir`` or ``$VANTIA_WORKSPACE_DIR`` or
    ``workspace/``. A workspace id may not escape the store root
    (``..`` / absolute paths are refused). Returns ``(source, store_path)``
    where ``store_path`` is the resolved file when one was read from the
    store (``None`` for explicit sources).
    """
    if resume is not None:
        return resume, None
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
    return target, target


def _begin_charge(
    user_id: str | None, operation: str, run_id: str, *ids: str
) -> tuple[CreditMeter | None, str | None]:
    """Task 11.4 pre-flight: tier allowance + R46 *before* any work starts.

    Returns ``(meter, ref)`` — ``(None, None)`` when no ``user_id`` was
    given, which keeps the un-metered local path unchanged. The ref makes
    the completion charge idempotent and auditable.
    """
    if not user_id:
        return None, None
    meter = default_meter()
    ref = f"{operation}:{run_id}:{':'.join(ids)}:{uuid.uuid4().hex[:12]}"
    meter.preflight(user_id, operation)
    return meter, ref


def _end_charge(
    meter: CreditMeter | None,
    user_id: str | None,
    operation: str,
    ref: str | None,
    *,
    meta: dict | None = None,
) -> dict | None:
    """Task 11.4 completion charge — only after the caller succeeded."""
    if meter is None or user_id is None or ref is None:
        return None
    return meter.charge(user_id, operation, ref, meta=meta)


def run_ats_scan(
    workspace_id: str,
    file_id: str,
    job_url: str,
    *,
    resume: str | bytes | dict | None = None,
    fetcher: Fetcher | None = None,
    store_dir: str | None = None,
    run_id: str = "0",
    user_id: str | None = None,
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

    Task 11.4: pass ``user_id`` to meter the run — pre-flight (allowance +
    R46) before any work, ``cv_scan`` charged only on success and reported
    in ``credits``; without ``user_id`` nothing about the run changes.
    """
    meter, charge_ref = _begin_charge(user_id, "cv_scan", run_id, workspace_id, file_id)
    report_path: str | None = None
    source, store_path = _resolve_upload(workspace_id, file_id, resume, store_dir)
    if store_path is not None:
        report_path = store_path + ".ats.json"

    parsed = parse_resume(source)
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
        "credits": _end_charge(
            meter,
            user_id,
            "cv_scan",
            charge_ref,
            meta={"pipeline": "9.5", "workspace_id": workspace_id, "file_id": file_id},
        ),
    }


def run_cv_improvement(
    workspace_id: str,
    file_id: str,
    *,
    resume: str | bytes | dict | None = None,
    store_dir: str | None = None,
    job_description: str = "",
    job_title: str = "",
    client: LLMClient | None = None,
    chain: list | None = None,
    run_id: str = "0",
    user_id: str | None = None,
) -> dict:
    """Upload -> parse -> improve -> persist (v4.0 §11, task 10.2).

    Deterministic ship layer (fact-preserving edits only); pass
    ``job_description``/``job_title`` to enable keyword mirroring, and
    ``client``/``chain`` for the optional LLM polish. The upload is read
    before any work (same resolution + traversal rules as 9.5) and the
    payload validates against ``cv_improvement.schema.json``.

    Task 11.4: with ``user_id`` the run is metered — ``cv_improvement``
    pre-flighted (allowance + R46) before any work and charged only on
    success; the charge lands in ``credits``.
    """
    meter, charge_ref = _begin_charge(user_id, "cv_improvement", run_id, workspace_id, file_id)
    source, store_path = _resolve_upload(workspace_id, file_id, resume, store_dir)
    parsed = parse_resume(source)
    artifact = improve_cv(
        parsed,
        original_cv_id=file_id,
        job_description=job_description,
        job_title=job_title,
        client=client,
        chain=chain,
        run_id=run_id,
    )
    report_path = store_path + ".improve.json" if store_path else None
    if report_path is not None:
        atomic_write_json(report_path, artifact.payload)
    return {
        "pipeline": {
            "task": "10.2",
            "workspace_id": workspace_id,
            "file_id": file_id,
            "run_id": run_id,
        },
        "improvement": artifact.payload,
        "provider": artifact.provider,
        "polished": artifact.polished,
        "fallback": artifact.fallback,
        "envelope": artifact.envelope,
        "report_path": report_path,
        "parser": {**parsed.metadata, "warnings": list(parsed.parse_warnings)},
        "credits": _end_charge(
            meter,
            user_id,
            "cv_improvement",
            charge_ref,
            meta={"pipeline": "10.2", "workspace_id": workspace_id, "file_id": file_id},
        ),
    }


def run_cover_letter(
    workspace_id: str,
    resume_id: str,
    job_url: str,
    *,
    resume: str | bytes | dict | None = None,
    fetcher: Fetcher | None = None,
    store_dir: str | None = None,
    tone: str = "professional",
    language: str = "en",
    client: LLMClient | None = None,
    chain: list | None = None,
    run_id: str = "0",
    user_id: str | None = None,
) -> dict:
    """Upload -> parse -> load posting -> letter -> persist (v4.0 §12, task 10.4).

    Deterministic ship layer writes only from the resume's facts and the
    posting's facts; the posting is loaded through the standard loader
    (robots + rate limit + closed-refusal) and the payload validates
    against ``cover_letter.schema.json``.

    Task 11.4: with ``user_id`` the run is metered — ``cover_letter``
    pre-flighted (allowance + R46) before any work (including the fetch)
    and charged only on success; the charge lands in ``credits``.
    """
    meter, charge_ref = _begin_charge(user_id, "cover_letter", run_id, workspace_id, resume_id)
    source, store_path = _resolve_upload(workspace_id, resume_id, resume, store_dir)
    parsed = parse_resume(source)
    listing = load_listing(job_url, fetcher)
    if not listing.is_active():
        raise FetchError(
            f"listing is no longer active: {job_url}",
            code="listing_inactive",
            url=job_url,
            closes_at=listing.closes_at,
        )
    artifact = generate_cover_letter(
        parsed,
        listing,
        resume_id=resume_id,
        tone=tone,
        language=language,
        client=client,
        chain=chain,
        run_id=run_id,
    )
    report_path = store_path + ".cover.json" if store_path else None
    if report_path is not None:
        atomic_write_json(report_path, artifact.payload)
    return {
        "pipeline": {
            "task": "10.4",
            "workspace_id": workspace_id,
            "resume_id": resume_id,
            "job_url": job_url,
            "run_id": run_id,
        },
        "job": asdict(listing),
        "cover_letter": artifact.payload,
        "provider": artifact.provider,
        "polished": artifact.polished,
        "fallback": artifact.fallback,
        "envelope": artifact.envelope,
        "report_path": report_path,
        "parser": {**parsed.metadata, "warnings": list(parsed.parse_warnings)},
        "credits": _end_charge(
            meter,
            user_id,
            "cover_letter",
            charge_ref,
            meta={"pipeline": "10.4", "workspace_id": workspace_id, "file_id": resume_id},
        ),
    }
