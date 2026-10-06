"""Academic credential mapper (task 3.4).

Bridges the equivalence registry (task 2.4) and the scholarship
database (task 3.1): resolve the applicant's qualification, then
compare its verified EQF level to the program's entry requirement.

Three-valued outcome — ``True`` (meets), ``False`` (below), ``None``
(could not verify: unknown credential or an unverified crosswalk) —
never a fabricated "you qualify".
"""

from __future__ import annotations

from ..credentials import equivalence
from .database import get_scholarship

__all__ = ["map_credential"]


def map_credential(
    scholarship_id: str, credential_query: str, *, country: str | None = None
) -> dict[str, object]:
    """Map ``credential_query`` onto ``scholarship_id``'s entry level.

    ``country`` is the credential's issuing country (registry filter,
    e.g. ``"NG"`` to disambiguate NG-HND from GB-HND).
    """
    sch = get_scholarship(scholarship_id)
    cred = equivalence(credential_query, country=country)
    raw = cred["match"]
    match: dict[str, object] | None = raw if isinstance(raw, dict) else None

    meets: bool | None
    if match is None:
        meets = None
        advice = (
            f"credential not found in the equivalence registry — {cred['advice']}. "
            f"{sch.name} entry level: EQF {sch.min_eqf_level} or equivalent."
        )
    else:
        level = match.get("eqf_level")
        if not isinstance(level, int):
            meets = None
            advice = (
                "level could not be verified from the embedded crosswalks — "
                f"{cred['advice']} Programme entry level: EQF {sch.min_eqf_level} "
                "or equivalent."
            )
        else:
            meets = level >= sch.min_eqf_level
            verdict = (
                f"meets the entry level (EQF {level} ≥ {sch.min_eqf_level})"
                if meets
                else f"falls short of the entry level (EQF {level} < {sch.min_eqf_level})"
            )
            advice = f"{sch.name}: credential {verdict}. Source: {cred['advice']}"

    return {
        "scholarship": {
            "id": sch.id,
            "name": sch.name,
            "level": sch.level,
            "min_eqf_level": sch.min_eqf_level,
            "url": sch.url,
        },
        "credential_query": credential_query,
        "issuing_country": country.upper() if country else None,
        "credential": match,
        "meets_level": meets,
        "required_eqf_level": sch.min_eqf_level,
        "advice": advice,
    }
