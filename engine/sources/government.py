"""Government job portals — jobs listed directly on state sites (session 7).

Policy: government portals are first-class sources; we fetch **all live
jobs** from them (sponsorship or not) and drop only postings whose
closing date has passed.

Implemented source:

* **Germany — Federal Employment Agency** (Bundesagentur für Arbeit).
  Endpoint, headers and response shape verified against the official
  ``bundesAPI/jobsuche-api`` example: ``GET .../pc/v4/app/jobs`` with the
  public ``X-API-Key: jobboerse-jobsuche`` and the app User-Agent (plain
  browser requests get 403 — that is why the headers matter).

Other countries' official portals are catalogued in
:mod:`engine.sources.countries` with their ``gov_jobs_api`` /
``pes_url`` entries; add an adapter here as each API is verified.
"""

from __future__ import annotations

import base64
import json
from urllib.parse import quote

from ..errors import FetchError
from .fetch import Fetcher
from .portals.base import (
    JobListing,
    ensure_active,
    filter_active,
    iso_date,
    strip_html,
)

SEARCH_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs"
DETAIL_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{refnr}"
#: Public API key shipped with the official app / SDK examples.
DEFAULT_API_KEY = "jobboerse-jobsuche"
DEFAULT_USER_AGENT = (
    "Jobsuche/2.9.2 (de.arbeitsagentur.jobboerse; build:1077; iOS 15.1.0) Alamofire/5.4.4"
)


class FederalEmploymentAgency:
    """German government jobs source (``portal="de-arbeitsagentur"``)."""

    name = "de-arbeitsagentur"
    country = "DE"
    domains = ("rest.arbeitsagentur.de", "www.arbeitsagentur.de")

    def __init__(
        self,
        fetcher: Fetcher | None = None,
        *,
        api_key: str | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        import os

        self.fetcher = fetcher if fetcher is not None else Fetcher()
        self.api_key = api_key or os.environ.get("VANTIA_AA_API_KEY", "").strip() or DEFAULT_API_KEY
        self.user_agent = user_agent

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "User-Agent": self.user_agent}

    # ── public API ─────────────────────────────────────────────────────
    def search(
        self,
        query: str,
        *,
        location: str = "",
        size: int = 25,
        page: int = 1,
        radius_km: int = 25,
    ) -> list[JobListing]:
        """Live jobs for ``query`` — active postings only."""
        result = self.fetcher.fetch(
            SEARCH_URL,
            params={
                "angebotsart": "1",
                "page": str(page),
                "pav": "false",
                "size": str(size),
                "umkreis": str(radius_km),
                "was": query,
                "wo": location,
            },
            headers=self._headers(),
        )
        payload = _json(result, SEARCH_URL)
        items = payload.get("stellenangebote") or []
        if not isinstance(items, list):
            raise FetchError("unexpected AA search response", url=SEARCH_URL)
        return filter_active([self._parse(item) for item in items[:size]])

    def load(self, refnr: str) -> JobListing:
        """Fetch one posting by its AA reference number (``refnr``)."""
        token = quote(base64.b64encode(refnr.encode("utf-8")).decode("ascii"), safe="")
        url = DETAIL_URL.format(refnr=token)
        result = self.fetcher.fetch(url, headers=self._headers())
        payload = _json(result, url)
        return ensure_active(self._parse(payload, url=url))

    # ── parsing (defensive across AA v4 key spellings) ─────────────────
    def _parse(self, item: dict, *, url: str = "") -> JobListing:
        if not isinstance(item, dict):
            raise FetchError("unexpected AA job record", url=url)
        refnr = str(item.get("refnr") or item.get("refNr") or "")
        title = (
            item.get("titel")
            or item.get("stellenangebotsTitel")
            or item.get("stellenangebotstitel")
            or item.get("beruf")
            or ""
        )
        employer = item.get("arbeitgeber") or item.get("firma") or ""
        location = item.get("ort") or item.get("arbeitsort") or item.get("region") or ""
        description_raw = (
            item.get("stellenbeschreibung")
            or item.get("aufgaben")
            or item.get("beschreibung")
            or item.get("text")
            or ""
        )
        extra = {"source": self.name}
        if refnr:
            extra["refnr"] = refnr
        return JobListing(
            portal=self.name,
            external_id=refnr,
            title=str(title),
            company=str(employer)
            if not isinstance(employer, dict)
            else str(employer.get("name", "")),
            location=str(location)
            if not isinstance(location, dict)
            else str(location.get("ort", "")),
            url=str(item.get("url") or item.get("weiterleitungUrl") or url),
            posted_at=iso_date(
                item.get("einstellungsdatum") or item.get("veroeffentlichungsdatum")
            ),
            description=strip_html(str(description_raw)) if description_raw else "",
            country=self.country,
            closes_at=iso_date(
                item.get("ablaufdatum")
                or item.get("gueltigBis")
                or item.get("veroeffentlichungBis")
                or item.get("closingDate")
            ),
            extra=extra,
        )


def _json(result, url: str) -> dict:  # type: ignore[no-untyped-def]
    try:
        payload = json.loads(result.content)
    except json.JSONDecodeError as exc:
        raise FetchError(f"non-JSON government response for {url}", url=url) from exc
    if not isinstance(payload, dict):
        raise FetchError(f"unexpected government response shape for {url}", url=url)
    return payload
