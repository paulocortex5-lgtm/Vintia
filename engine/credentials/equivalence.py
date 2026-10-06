"""Credential equivalence lookup (task 2.4).

Translates a user's qualification into a comparable European reference —
the README promise: *NVQ, HND, BTS, CAP, GPA ↔ ECTS*.

Design rules (repo-wide: no invented facts, no guessed URLs):

* Every :class:`Credential` row carries a ``basis`` note naming the
  published source it was derived from (GOV.UK qualification levels,
  UHR/ENIC-Sweden assessments, French RNCP levels, the German DQR,
  the Bologna cycle credit loads).
* ``eqf_level`` is asserted **only** where a verified crosswalk exists
  (UHR's "NQF level 5 = EQF level 5", the Bologna first/second/third
  cycles, the one-to-one RNCP/DQR referencing). Where no crosswalk is
  embedded the field is ``None`` and the advice is *recognise manually
  via ENIC-NARIC* — an honest gap beats a confident wrong number.
* The registry is a **static, deterministic** ship layer. A live remote
  lookup exists (:func:`remote_lookup`) but is opt-in: the endpoint is
  owner-configured (``VANTIA_EQUIVALENCE_ENDPOINT``), never guessed.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass

from ..errors import FetchError, VantiaError
from ..sources.fetch import Fetcher

__all__ = [
    "CREDENTIALS",
    "ECTS_GRADES",
    "Credential",
    "EctsGrade",
    "degree_in_country",
    "describe",
    "equivalence",
    "gpa_to_ects",
    "lookup",
    "remote_lookup",
]


@dataclass(frozen=True)
class Credential:
    """One qualification in the equivalence registry."""

    id: str
    title: str
    country: str  # ISO 3166-1 alpha-2 issuing country, "INT" = international
    framework: str  # "FHEQ", "RNCP", "DQR", "Bologna", ...
    level: str  # framework level label ("level 5", "niveau 5", ...)
    cycle: str  # secondary | vocational | sub_degree | bachelor | master | doctorate
    eqf_level: int | None = None  # asserted only with a verified crosswalk
    ects: int | None = None  # nominal ECTS credit load where meaningful
    aliases: tuple[str, ...] = ()
    basis: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "country": self.country,
            "framework": self.framework,
            "level": self.level,
            "cycle": self.cycle,
            "eqf_level": self.eqf_level,
            "ects": self.ects,
            "aliases": list(self.aliases),
            "basis": self.basis,
        }


@dataclass(frozen=True)
class EctsGrade:
    """One row of the ECTS grade scale (A excellent … F fail)."""

    code: str
    descriptor: str
    min_ratio: float

    def __str__(self) -> str:
        return f"{self.code} ({self.descriptor})"


#: ECTS Users' Guide grade descriptors with this module's ratio bands.
ECTS_GRADES: tuple[EctsGrade, ...] = (
    EctsGrade("A", "excellent", 0.90),
    EctsGrade("B", "very good", 0.80),
    EctsGrade("C", "good", 0.70),
    EctsGrade("D", "satisfactory", 0.60),
    EctsGrade("E", "pass", 0.50),
    EctsGrade("F", "fail", 0.0),
)

_RNCP_BASIS = "French RNCP levels (referenced 1:1 to EQF); Bologna cycle credit loads"
_DQR_BASIS = "Deutscher Qualifikationsrahmen (referenced 1:1 to EQF); Bologna cycle credit loads"


def _c(
    id: str,
    title: str,
    country: str,
    framework: str,
    level: str,
    cycle: str,
    *,
    eqf: int | None = None,
    ects: int | None = None,
    aliases: tuple[str, ...] = (),
    basis: str = "",
) -> Credential:
    return Credential(
        id=id,
        title=title,
        country=country,
        framework=framework,
        level=level,
        cycle=cycle,
        eqf_level=eqf,
        ects=ects,
        aliases=aliases,
        basis=basis,
    )


#: Curated registry — extend by appending rows, never by guessing facts.
CREDENTIALS: tuple[Credential, ...] = (
    # ── United Kingdom (FHEQ/RQF/NVQ) ──────────────────────────────────
    _c(
        "gb-nvq-2",
        "NVQ Level 2",
        "GB",
        "RQF/NVQ",
        "level 2",
        "vocational",
        aliases=("nvq 2", "nvq level 2", "national vocational qualification level 2"),
        basis="listed at level 2 on GOV.UK; EQF reference not asserted (no verified crosswalk embedded)",
    ),
    _c(
        "gb-nvq-3",
        "NVQ Level 3",
        "GB",
        "RQF/NVQ",
        "level 3",
        "vocational",
        aliases=("nvq 3", "nvq level 3", "national vocational qualification level 3"),
        basis="listed at level 3 on GOV.UK; EQF reference not asserted (no verified crosswalk embedded)",
    ),
    _c(
        "gb-a-level",
        "A level",
        "GB",
        "FHEQ",
        "level 3",
        "secondary",
        aliases=("a level", "a levels", "as level", "advanced level", "gce advanced level"),
        basis="listed at level 3 on GOV.UK; EQF reference not asserted (no verified crosswalk embedded)",
    ),
    _c(
        "gb-hnc",
        "Higher National Certificate (HNC)",
        "GB",
        "FHEQ",
        "level 4",
        "sub_degree",
        ects=60,
        aliases=("hnc", "higher national certificate"),
        basis="120 UK credits halved from UHR's verified 240 CATS = 120 ECTS; EQF not asserted",
    ),
    _c(
        "gb-hnd",
        "Higher National Diploma (HND)",
        "GB",
        "FHEQ",
        "level 5",
        "sub_degree",
        eqf=5,
        ects=120,
        aliases=("hnd", "higher national diploma", "btec higher national diploma"),
        basis="UHR/ENIC-Sweden: 240 CATS = 120 ECTS and NQF level 5 = EQF level 5",
    ),
    _c(
        "gb-foundation-degree",
        "Foundation degree",
        "GB",
        "FHEQ",
        "level 5",
        "sub_degree",
        eqf=5,
        ects=120,
        aliases=("foundation degree", "fd"),
        basis="FHEQ level 5 (GOV.UK) with UHR's level-5 = EQF-5 reference; 240 UK credits = 120 ECTS",
    ),
    _c(
        "gb-bachelor",
        "Bachelor's degree (BA / BSc, honours)",
        "GB",
        "FHEQ",
        "level 6",
        "bachelor",
        eqf=6,
        ects=180,
        aliases=("ba", "bsc", "ba hons", "bsc hons", "honours degree"),
        basis="FHEQ level 6; 360 UK credits = 180 ECTS (UHR 2:1 credit ratio); EQF 6 = first cycle",
    ),
    _c(
        "gb-master",
        "Master's degree (MA / MSc)",
        "GB",
        "FHEQ",
        "level 7",
        "master",
        eqf=7,
        ects=90,
        aliases=("ma", "msc"),
        basis="FHEQ level 7; one-year taught master's 180 UK credits = 90 ECTS",
    ),
    _c(
        "gb-doctorate",
        "Doctorate (PhD / DPhil)",
        "GB",
        "FHEQ",
        "level 8",
        "doctorate",
        eqf=8,
        aliases=("dphil",),
        basis="FHEQ level 8; EQF 8 = doctoral cycle (no nominal ECTS — research degree)",
    ),
    # ── International (Bologna cycles) ─────────────────────────────────
    _c(
        "int-associate",
        "Short-cycle tertiary / associate degree",
        "INT",
        "Bologna/ISCED 5",
        "short cycle",
        "sub_degree",
        eqf=5,
        ects=120,
        aliases=("associate degree", "short cycle", "two year degree", "2 year degree"),
        basis="60 US semester credits ≈ 120 ECTS (30 US credits = one 60-ECTS academic year)",
    ),
    _c(
        "int-bachelor",
        "Bachelor's degree (first cycle)",
        "INT",
        "Bologna",
        "first cycle",
        "bachelor",
        eqf=6,
        ects=180,
        aliases=(
            "bachelor",
            "bachelor degree",
            "undergraduate degree",
            "first cycle",
            "llb",
            "beng",
        ),
        basis="Bologna first cycle, nominal 180 ECTS (3 years); EQF level 6",
    ),
    _c(
        "int-bachelor-4yr",
        "Bachelor's degree, four-year (B.E. / B.Tech / BS)",
        "INT",
        "Bologna",
        "first cycle (4 yr)",
        "bachelor",
        eqf=6,
        ects=240,
        aliases=("btech", "b tech", "bachelor of technology", "bachelor of engineering"),
        basis="4-year bachelor's = 240 ECTS on the US credit convention (120 credits ≈ 240 ECTS); EQF level 6",
    ),
    _c(
        "int-master",
        "Master's degree (second cycle)",
        "INT",
        "Bologna",
        "second cycle",
        "master",
        eqf=7,
        ects=120,
        aliases=("master", "master degree", "second cycle", "postgraduate", "mba", "meng"),
        basis="Bologna second cycle, nominal 120 ECTS (2 years); EQF level 7",
    ),
    _c(
        "int-doctorate",
        "Doctorate (third cycle)",
        "INT",
        "Bologna",
        "third cycle",
        "doctorate",
        eqf=8,
        aliases=("doctorate", "doctoral degree", "third cycle", "ph.d"),
        basis="Bologna third cycle; EQF level 8 (no nominal ECTS — research degree)",
    ),
    # ── France (RNCP) ──────────────────────────────────────────────────
    _c(
        "fr-cap",
        "CAP (Certificat d'Aptitude Professionnelle)",
        "FR",
        "RNCP",
        "niveau 3",
        "vocational",
        eqf=3,
        aliases=("cap", "certificat d'aptitude professionnelle"),
        basis=_RNCP_BASIS,
    ),
    _c(
        "fr-bac",
        "Baccalauréat",
        "FR",
        "RNCP",
        "niveau 4",
        "secondary",
        eqf=4,
        aliases=("baccalaureat", "bac", "baccalauréat général", "baccalaureat general"),
        basis=_RNCP_BASIS,
    ),
    _c(
        "fr-bts",
        "BTS (Brevet de Technicien Supérieur)",
        "FR",
        "RNCP",
        "niveau 5",
        "sub_degree",
        eqf=5,
        ects=120,
        aliases=("bts", "brevet de technicien superieur", "brevet de technicien supérieur"),
        basis=_RNCP_BASIS + "; BTS = 120 ECTS (2 ans)",
    ),
    _c(
        "fr-licence",
        "Licence",
        "FR",
        "RNCP",
        "niveau 6",
        "bachelor",
        eqf=6,
        ects=180,
        aliases=("licence", "licence generale", "bachelor fr"),
        basis=_RNCP_BASIS + "; Licence = 180 ECTS (3 ans)",
    ),
    _c(
        "fr-master",
        "Master",
        "FR",
        "RNCP",
        "niveau 7",
        "master",
        eqf=7,
        ects=120,
        aliases=("master 2", "m2 fr"),
        basis=_RNCP_BASIS + "; Master = 120 ECTS (2 ans après licence)",
    ),
    _c(
        "fr-doctorat",
        "Doctorat",
        "FR",
        "RNCP",
        "niveau 8",
        "doctorate",
        eqf=8,
        aliases=("doctorat", "these fr"),
        basis=_RNCP_BASIS,
    ),
    # ── Germany (DQR) ──────────────────────────────────────────────────
    _c(
        "de-ausbildung",
        "Duale Ausbildung (Berufsausbildung)",
        "DE",
        "DQR",
        "NQR level 3",
        "vocational",
        eqf=3,
        aliases=("ausbildung", "berufsausbildung", "duale ausbildung", "apprenticeship de"),
        basis=_DQR_BASIS + "; abgeschlossene Berufsausbildung = NQR 3",
    ),
    _c(
        "de-abitur",
        "Abitur (Allgemeine Hochschulreife)",
        "DE",
        "DQR",
        "NQR level 4",
        "secondary",
        eqf=4,
        aliases=("abitur", "allgemeine hochschulreife", "reifezeugnis", "fachabitur"),
        basis=_DQR_BASIS,
    ),
    _c(
        "de-meister",
        "Meister / Techniker",
        "DE",
        "DQR",
        "NQR level 6",
        "vocational",
        eqf=6,
        aliases=("meister", "staatlich geprüfter meister", "techniker", "meisterbrief"),
        basis=_DQR_BASIS + "; Meister/Techniker = NQR 6",
    ),
    _c(
        "de-bachelor",
        "Bachelor",
        "DE",
        "DQR",
        "NQR level 6",
        "bachelor",
        eqf=6,
        ects=180,
        aliases=("bachelor de", "bachelor degree de"),
        basis=_DQR_BASIS + "; Bachelor = NQR 6, typisch 180 ECTS",
    ),
    _c(
        "de-master",
        "Master",
        "DE",
        "DQR",
        "NQR level 7",
        "master",
        eqf=7,
        ects=120,
        aliases=("master de", "master degree de"),
        basis=_DQR_BASIS + "; Master = NQR 7, typisch 120 ECTS",
    ),
    _c(
        "de-promotion",
        "Promotion (Doktor)",
        "DE",
        "DQR",
        "NQR level 8",
        "doctorate",
        eqf=8,
        aliases=("promotion", "doktortitel", "promotion de"),
        basis=_DQR_BASIS,
    ),
    # ── Nigeria (NBTE national diplomas — honest gaps) ─────────────────
    _c(
        "ng-ond",
        "Ordinary National Diploma (OND)",
        "NG",
        "NBTE National Diploma",
        "national diploma",
        "sub_degree",
        aliases=("ond", "ordinary national diploma", "national diploma"),
        basis="NBTE post-SSCE National Diploma; no verified EQF/ECTS crosswalk embedded — recognise via ENIC-NARIC",
    ),
    _c(
        "ng-hnd",
        "Higher National Diploma (HND), Nigeria",
        "NG",
        "NBTE National Diploma",
        "higher national diploma",
        "sub_degree",
        aliases=("hnd nigeria", "hnd ng", "higher national diploma nigeria"),
        basis="NBTE post-OND higher diploma; no verified EQF/ECTS crosswalk embedded — recognise via ENIC-NARIC",
    ),
)


# ── matching ───────────────────────────────────────────────────────────


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


#: pre-computed normalised search texts, registry order preserved
_INDEX: tuple[tuple[Credential, tuple[str, ...]], ...] = tuple(
    (cred, (_norm(cred.title), *(_norm(a) for a in cred.aliases))) for cred in CREDENTIALS
)

#: words that carry no identity on their own (a bare "degree" must not
#: match "foundation degree" — weak overlap fabricates equivalences)
_STOPWORDS: frozenset[str] = frozenset(
    {"of", "the", "a", "an", "in", "on", "and", "for", "to", "or", "by", "at", "degree", "degrees"}
)


def _significant(tokens: set[str]) -> set[str]:
    return {t for t in tokens if len(t) > 1 and t not in _STOPWORDS}


def lookup(query: str, *, country: str | None = None) -> list[Credential]:
    """Registry matches for ``query``, best first.

    Ranking: exact title/alias (0) > query-contained-in-text (1) >
    text-contained-in-query (2) > token overlap (3); ties keep registry
    order. ``country`` narrows to that issuer country plus international
    rows (``"INT"``) — an unqualified "hnd" never returns Nigeria's HND
    unless ``country="NG"``.
    """
    q = _norm(query)
    if not q:
        return []
    code = country.strip().upper() if country else None
    q_tokens = set(q.split())
    q_sig = _significant(q_tokens)
    hits: list[tuple[float, int, int, Credential]] = []
    for index, (cred, texts) in enumerate(_INDEX):
        if code and cred.country not in (code, "INT"):
            continue
        best: tuple[float, int] | None = None
        for text in texts:
            text_tokens = set(text.split())
            overlap = len(q_tokens & text_tokens)
            if text == q:
                rank = (0.0, 0)
            elif q in text:
                rank = (1.0, -overlap)
            elif text in q:
                rank = (2.0, -overlap)
            elif q_sig and q_sig <= _significant(text_tokens):
                # every meaningful query word appears in this text
                rank = (3.0, -overlap)
            else:
                continue
            if best is None or rank < best:
                best = rank
        if best is not None:
            hits.append((best[0], best[1], index, cred))
    hits.sort(key=lambda hit: (hit[0], hit[1], hit[2]))
    return [cred for _, _, _, cred in hits]


def describe(query: str, *, country: str | None = None) -> Credential | None:
    """Best match for ``query`` (or ``None`` — never a guess)."""
    matches = lookup(query, country=country)
    return matches[0] if matches else None


# ── translation into a target country ──────────────────────────────────

_DEGREE_TITLES: dict[str, dict[int, str]] = {
    "GB": {
        5: "Higher National Diploma / foundation-degree level (below bachelor's)",
        6: "Bachelor's degree (BA / BSc)",
        7: "Master's degree (MA / MSc)",
        8: "Doctorate (PhD / DPhil)",
    },
    "FR": {5: "BTS / DUT — cycle court (below licence)", 6: "Licence", 7: "Master", 8: "Doctorat"},
    "DE": {
        5: "short-cycle tertiary / advanced vocational level (below Bachelor)",
        6: "Bachelor",
        7: "Master",
        8: "Promotion (Doktor)",
    },
    "IE": {
        5: "advanced certificate level (below Bachelor)",
        6: "Honours Bachelor Degree (NFQ level 8)",
        7: "Masters Degree (NFQ level 9)",
        8: "Doctoral Degree (NFQ level 10)",
    },
    "SE": {
        5: "short-cycle higher education (below kandidatexamen)",
        6: "Kandidatexamen (180 hp)",
        7: "Masterexamen (120 hp)",
        8: "Doktorsexamen",
    },
    "CA": {
        5: "college diploma / associate degree (below bachelor's)",
        6: "Bachelor's degree",
        7: "Master's degree",
        8: "Doctorate",
    },
    "AU": {
        5: "Advanced Diploma / Associate Degree (AQF level 6, below Bachelor)",
        6: "Bachelor degree (AQF level 7)",
        7: "Master's degree (AQF level 8)",
        8: "Doctoral degree (AQF level 9)",
    },
}

_GENERIC_DEGREE: dict[int, str] = {
    5: "short-cycle tertiary / sub-degree level (below bachelor's)",
    6: "bachelor's degree or equivalent",
    7: "master's degree or equivalent",
    8: "doctorate or equivalent",
}


def degree_in_country(eqf_level: int | None, iso2: str | None) -> str | None:
    """Title an ``eqf_level`` carries in ``iso2``'s system (``None`` below 5)."""
    if eqf_level is None or not iso2:
        return None
    table = _DEGREE_TITLES.get(iso2.strip().upper())
    if table and eqf_level in table:
        return table[eqf_level]
    if eqf_level in _GENERIC_DEGREE:
        return _GENERIC_DEGREE[eqf_level]
    return None


def equivalence(
    query: str, *, country: str | None = None, target_country: str | None = None
) -> dict[str, object]:
    """Product-facing payload: translate ``query`` and place it abroad.

    Always returns a dict; ``match`` is ``None`` when nothing matches
    (the UI shows "not found" rather than a fabricated equivalence).
    ``advice`` states the provenance of the claim — or the honest
    instruction to seek ENIC-NARIC recognition when no crosswalk is
    embedded.
    """
    matches = lookup(query, country=country)
    best = matches[0] if matches else None
    target_title = degree_in_country(best.eqf_level, target_country) if best else None
    if best is None:
        advice = (
            "not in the embedded registry — verify with the ENIC-NARIC centre in the "
            "target country (enic-naric.net) before relying on any equivalence"
        )
    elif best.eqf_level is None:
        advice = (
            "credential found, but no verified EQF/ECTS crosswalk is embedded for it — "
            "verify with the ENIC-NARIC centre (enic-naric.net) before relying on it"
        )
    else:
        advice = f"equivalence derived from: {best.basis}"
    return {
        "query": query,
        "match": best.to_dict() if best else None,
        "alternatives": [c.to_dict() for c in matches[1:4]],
        "target_country": target_country.strip().upper() if target_country else None,
        "target_title": target_title,
        "advice": advice,
    }


# ── grade conversion (GPA ↔ ECTS) ──────────────────────────────────────


def gpa_to_ects(value: float, *, scale: float = 4.0) -> EctsGrade:
    """Approximate GPA → ECTS grade (A excellent … F fail).

    Bands are ratio-based (``value/scale``: ≥0.90 A, ≥0.80 B, ≥0.70 C,
    ≥0.60 D, ≥0.50 E, else F) — the common US-letter percentage
    convention. Institutions publish their own tables; pass ``scale``
    for other systems (10, 100, 5) and treat the result as guidance,
    not an official recognition.
    """
    if scale <= 0:
        raise VantiaError(
            f"grade scale must be positive, got {scale}", code="grade_scale_invalid", scale=scale
        )
    if value < 0 or value > scale:
        raise VantiaError(
            f"grade {value} outside 0..{scale}",
            code="grade_out_of_range",
            value=value,
            scale=scale,
        )
    ratio = value / scale
    for grade in ECTS_GRADES:
        if ratio >= grade.min_ratio:
            return grade
    return ECTS_GRADES[-1]  # pragma: no cover — F's band covers ratio >= 0


# ── optional live lookup (owner-configured endpoint, never guessed) ────


def remote_lookup(
    query: str, *, fetcher: Fetcher | None = None, endpoint: str | None = None
) -> list[Credential]:
    """Query a remote comparability service through the polite :class:`Fetcher`.

    The endpoint is **owner-configured** (``endpoint`` argument or
    ``VANTIA_EQUIVALENCE_ENDPOINT``); with none set this raises
    ``equivalence_endpoint_unconfigured`` instead of guessing a URL —
    the static registry above remains the shipping default.
    """
    url = (endpoint or "").strip() or os.environ.get("VANTIA_EQUIVALENCE_ENDPOINT", "").strip()
    if not url:
        raise VantiaError(
            "no equivalence endpoint configured; set VANTIA_EQUIVALENCE_ENDPOINT "
            "(owner-provided — Vantia never guesses data URLs)",
            code="equivalence_endpoint_unconfigured",
        )
    client = fetcher if fetcher is not None else Fetcher()
    result = client.fetch(url, params={"q": query})
    try:
        payload = json.loads(result.content)
    except json.JSONDecodeError as exc:
        raise FetchError(
            "equivalence endpoint returned non-JSON",
            code="equivalence_bad_payload",
            url=url,
        ) from exc
    rows = payload.get("results") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise FetchError(
            "equivalence endpoint payload must be a list or {'results': [...]}",
            code="equivalence_bad_payload",
            url=url,
        )
    return [_remote_row(row, i, url) for i, row in enumerate(rows)]


def _remote_row(row: object, index: int, url: str) -> Credential:
    if not isinstance(row, dict) or not row.get("title"):
        raise FetchError(
            f"equivalence row {index} is missing 'title'", code="equivalence_bad_payload", url=url
        )
    aliases = row.get("aliases")
    return Credential(
        id=str(row.get("id") or f"remote-{index}"),
        title=str(row["title"]),
        country=str(row.get("country") or "INT"),
        framework=str(row.get("framework") or "remote"),
        level=str(row.get("level") or ""),
        cycle=str(row.get("cycle") or ""),
        eqf_level=_int_or_none(row.get("eqf_level")),
        ects=_int_or_none(row.get("ects")),
        aliases=tuple(str(a) for a in aliases) if isinstance(aliases, list) else (),
        basis=str(row.get("basis") or f"remote lookup ({url})"),
    )


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None
