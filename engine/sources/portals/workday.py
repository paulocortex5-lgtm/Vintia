"""Workday CXS adapter (task 2.2, the "W" in W/G/L).

The Workday career-site API is POST-only and undocumented, but stable:

* list  — ``POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs``
  body ``{"appliedFacets": {}, "limit": N, "offset": 0, "searchText": ""}``
  → ``{"total": int, "jobPostings": [...]}`
* load  — ``POST .../wday/cxs/{tenant}/{site}/job/{jobPostingId}``
  → ``{"jobPostingInfo": {"jobDescription": "<html>...", ...}}``

``source`` for :meth:`search` is ``"{tenant}/{site}"`` (e.g.
``"amazon/Amazon"``). The ``wdN`` datacentre label defaults to ``wd5``
and is configurable per adapter instance.
"""

from __future__ import annotations

import json
from urllib.parse import unquote, urlsplit

from ...errors import FetchError
from ..fetch import Fetcher, FetchResult
from .base import JobListing, PortalAdapter, iso_date, strip_html


class WorkdayAdapter(PortalAdapter):
    name = "workday"
    domains = ("myworkdayjobs.com",)

    def __init__(self, fetcher: Fetcher | None = None, *, wd: int = 5) -> None:
        super().__init__(fetcher)
        self.wd = wd

    # ── public API ─────────────────────────────────────────────────────
    def search(self, source: str, *, limit: int = 25) -> list[JobListing]:
        tenant, site = self._split_source(source)
        url = self._base(tenant, site) + "/jobs"
        result = self.fetcher.post(
            url,
            json={"appliedFacets": {}, "limit": int(limit), "offset": 0, "searchText": ""},
        )
        payload = _json(result, url)
        if not isinstance(payload, dict):
            raise FetchError(f"unexpected Workday list response for {source}", url=url)
        postings = payload.get("jobPostings") or []
        return [self._parse(posting, tenant) for posting in postings[:limit]]

    def load(self, url: str) -> JobListing:
        tenant, site, job_id = self._split_job_url(url)
        detail_url = f"{self._base(tenant, site)}/job/{job_id}"
        result = self.fetcher.post(detail_url, json={})
        payload = _json(result, detail_url)
        info = payload.get("jobPostingInfo") or {}
        if not isinstance(info, dict):
            raise FetchError(f"unexpected Workday detail response for {url}", url=detail_url)
        description = info.get("jobDescription") or ""
        return JobListing(
            portal=self.name,
            external_id=str(info.get("jobPostingId") or job_id),
            title=info.get("title") or "",
            company=tenant,
            location=info.get("locationsText") or "",
            url=url,
            posted_at=iso_date(info.get("postedOn")),
            description=strip_html(description),
        )

    # ── internals ──────────────────────────────────────────────────────
    @staticmethod
    def _split_source(source: str) -> tuple[str, str]:
        parts = [p for p in source.split("/") if p.strip()]
        if len(parts) != 2:
            raise ValueError(f"Workday source must be 'tenant/site', got: {source!r}")
        return parts[0].strip(), parts[1].strip()

    def _base(self, tenant: str, site: str) -> str:
        return f"https://{tenant}.wd{self.wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"

    @classmethod
    def _split_job_url(cls, url: str) -> tuple[str, str, str]:
        parts = urlsplit(url)
        tenant = (parts.hostname or "").split(".")[0]
        segments = [unquote(s) for s in parts.path.split("/") if s]
        if "job" not in segments:
            raise ValueError(f"not a Workday job URL: {url}")
        i = segments.index("job")
        if i == 0 or i + 1 >= len(segments):
            raise ValueError(f"not a Workday job URL: {url}")
        return tenant, segments[i - 1], segments[i + 1]

    @classmethod
    def _parse(cls, posting: dict, tenant: str) -> JobListing:
        return JobListing(
            portal=cls.name,
            external_id=str(posting.get("jobPostingId") or posting.get("externalUrl") or ""),
            title=posting.get("title") or "",
            company=tenant,
            location=posting.get("locationsText") or "",
            url=posting.get("externalUrl") or "",
            posted_at=iso_date(posting.get("postedOn")),
            description="",  # list endpoint omits it; call load() for the body
        )


def _json(result: FetchResult, url: str) -> dict:
    try:
        return json.loads(result.content)
    except json.JSONDecodeError as exc:  # pragma: no cover — defensive
        raise FetchError(f"non-JSON Workday response for {url}", url=url) from exc
