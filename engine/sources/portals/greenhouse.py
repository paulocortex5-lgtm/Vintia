"""Greenhouse job-board adapter (task 2.2, the "G" in W/G/L).

Endpoints (public, no auth):

* list  — ``GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true``
* load  — ``GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{id}``

Hosted job URLs (``boards.greenhouse.io/...`` / ``job-boards.greenhouse.io/...``)
map back onto the API by token + job id.
"""

from __future__ import annotations

import html
import json
from urllib.parse import urlsplit

from ...errors import FetchError
from ..fetch import FetchResult
from .base import JobListing, PortalAdapter, ensure_active, filter_active, iso_date, strip_html

API = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseAdapter(PortalAdapter):
    name = "greenhouse"
    domains = ("boards.greenhouse.io", "job-boards.greenhouse.io", "boards-api.greenhouse.io")

    def search(self, source: str, *, limit: int = 25) -> list[JobListing]:
        token = source.strip().strip("/")
        result = self.fetcher.fetch(f"{API}/{token}/jobs", params={"content": "true"})
        payload = _json(result)
        if not isinstance(payload, dict):
            raise FetchError(
                f"unexpected Greenhouse list response for {token}", url=str(result.final_url)
            )
        jobs = payload.get("jobs", [])
        return filter_active([self._parse(job, token) for job in jobs[:limit]])

    def load(self, url: str) -> JobListing:
        token, job_id = self._split(url)
        result = self.fetcher.fetch(f"{API}/{token}/jobs/{job_id}")
        payload = _json(result)
        if not isinstance(payload, dict):
            raise FetchError(f"unexpected Greenhouse job response for {url}", url=url)
        return ensure_active(self._parse(payload, token))

    # ── internals ──────────────────────────────────────────────────────
    @staticmethod
    def _split(url: str) -> tuple[str, str]:
        parts = [p for p in urlsplit(url).path.split("/") if p]
        # {token}/jobs/{id}  (legacy and job-boards hosts share the shape)
        for i, seg in enumerate(parts):
            if seg == "jobs" and i >= 1 and i + 1 < len(parts):
                return parts[i - 1], parts[i + 1]
        raise ValueError(f"not a Greenhouse job URL: {url}")

    @classmethod
    def _parse(cls, job: dict, token: str) -> JobListing:
        content = job.get("content") or ""
        description = strip_html(html.unescape(content)) if content else ""
        location = (job.get("location") or {}).get("name") or ""
        return JobListing(
            portal=cls.name,
            external_id=str(job.get("id", "")),
            title=job.get("title") or "",
            company=job.get("company_name") or token,
            location=location,
            url=job.get("absolute_url") or "",
            posted_at=iso_date(job.get("updated_at") or job.get("first_published")),
            description=description,
            closes_at=iso_date(
                job.get("closes_at") or job.get("closing_date") or job.get("deadline")
            ),
        )


def _json(result: FetchResult) -> dict:
    try:
        return json.loads(result.content)
    except json.JSONDecodeError as exc:  # pragma: no cover — defensive
        from ...errors import FetchError

        raise FetchError(f"non-JSON Greenhouse response for {result.url}", url=result.url) from exc
