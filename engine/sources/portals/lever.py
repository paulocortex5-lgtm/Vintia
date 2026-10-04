"""Lever postings adapter (task 2.2, the "L" in W/G/L).

Endpoints (public, no auth — global and EU instances):

* list  — ``GET https://api.lever.co/v0/postings/{company}?mode=json``
          (``limit``/``skip`` are honoured; EU: ``api.eu.lever.co``)
* load  — ``GET https://api.lever.co/v0/postings/{company}/{uuid}``

Hosted URLs live on ``jobs.lever.co`` / ``jobs.eu.lever.co``.
"""

from __future__ import annotations

import json
from urllib.parse import urlsplit

from ...errors import FetchError
from ..fetch import FetchResult
from .base import (
    JobListing,
    PortalAdapter,
    ensure_active,
    epoch_ms_date,
    filter_active,
    iso_date,
    strip_html,
)

API_GLOBAL = "https://api.lever.co/v0/postings"
API_EU = "https://api.eu.lever.co/v0/postings"


class LeverAdapter(PortalAdapter):
    name = "lever"
    domains = ("jobs.lever.co", "jobs.eu.lever.co", "api.lever.co", "api.eu.lever.co")

    def search(self, source: str, *, limit: int = 25) -> list[JobListing]:
        company = source.strip().strip("/")
        result = self.fetcher.fetch(
            f"{API_GLOBAL}/{company}",
            params={"mode": "json", "limit": int(limit)},
        )
        postings = _json(result)
        if not isinstance(postings, list):
            raise FetchError(
                f"unexpected Lever list response for {company}", url=str(result.final_url)
            )
        return filter_active([self._parse(posting, company) for posting in postings[:limit]])

    def load(self, url: str) -> JobListing:
        company, uuid = self._split(url)
        api = API_EU if "jobs.eu.lever.co" in url or "api.eu.lever.co" in url else API_GLOBAL
        result = self.fetcher.fetch(f"{api}/{company}/{uuid}")
        payload = _json(result)
        if not isinstance(payload, dict):
            raise FetchError(f"unexpected Lever posting response for {url}", url=url)
        return ensure_active(self._parse(payload, company))

    # ── internals ──────────────────────────────────────────────────────
    @staticmethod
    def _split(url: str) -> tuple[str, str]:
        parts = [p for p in urlsplit(url).path.split("/") if p]
        if len(parts) >= 2:
            return parts[0], parts[1]
        raise ValueError(f"not a Lever job URL: {url}")

    @classmethod
    def _parse(cls, posting: dict, company: str) -> JobListing:
        categories = posting.get("categories") or {}
        created_ms = posting.get("createdAt")
        description = posting.get("descriptionPlain") or ""
        if not description and posting.get("lists"):
            description = "\n\n".join(
                str(section.get("text", "")) for section in posting["lists"] if section.get("text")
            )
        return JobListing(
            portal=cls.name,
            external_id=str(posting.get("id", "")),
            title=posting.get("text") or "",
            company=company,
            location=categories.get("location") or "",
            url=posting.get("hostedUrl") or "",
            posted_at=epoch_ms_date(created_ms) if isinstance(created_ms, (int, float)) else None,
            description=strip_html(description),
            closes_at=iso_date(
                posting.get("closes_at") or posting.get("deadline") or posting.get("closeDate")
            ),
            extra={
                key: str(value)
                for key, value in (
                    ("team", categories.get("team")),
                    ("commitment", categories.get("commitment")),
                    ("workplaceType", posting.get("workplaceType")),
                )
                if value
            },
        )


def _json(result: FetchResult) -> list | dict:
    try:
        return json.loads(result.content)
    except json.JSONDecodeError as exc:  # pragma: no cover — defensive
        from ...errors import FetchError

        raise FetchError(f"non-JSON Lever response for {result.url}", url=result.url) from exc
