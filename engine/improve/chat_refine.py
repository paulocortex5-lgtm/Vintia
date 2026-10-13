"""CV refinement chatbot (task 15.6).

Conversational refinement of an existing improved CV: each user message
produces a *new turn* (revised CV + change summary). The original
improved text is never overwritten — turns are append-only, and the
latest turn's ``revised_text`` is the current CV state.

Turn limits (R25): free 3, pro 20, business unlimited. Each accepted
turn costs 2,000 credits, debited **after** the turn is persisted
(R17/R18): when no LLM provider answers (or the model output fails the
schema), the handler returns ``status="incomplete"`` with an honest
``missing`` reason, records **no** turn and charges **nothing**.

Store: local-first JSON under ``$VANTIA_FEATURES_DIR`` (default
``.vantia/features``), keyed by ``cv_improvement_id``; a Supabase
write-through mirror is best-effort, never raising (STEP K).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from typing import Any

from ..credits import default_ledger, ensure_allowance
from ..credits.tiers import tier_of
from ..errors import InsufficientCredits, TurnLimitExceeded, VantiaError
from ..json_utils import atomic_write_json, load_json, validate
from ..logging_config import utc_now

__all__ = ["REFINE_COST", "TURN_LIMITS", "refine", "turns_for"]

LOGGER = logging.getLogger("vantia.improve.chat_refine")

#: Credit price per accepted turn (task 15.6 §10.8).
REFINE_COST = 2000

#: R25 — turn caps per tier.
TURN_LIMITS: dict[str, int] = {"free": 3, "pro": 20, "business": 10**9}

PROMPT_VERSION = "1.0.0"

_store_lock = threading.RLock()


def _default_dir() -> str:
    return os.environ.get("VANTIA_FEATURES_DIR", os.path.join(".vantia", "features"))


def _store_file() -> str:
    return os.path.join(_default_dir(), "cv_refinement_turns.json")


def _schema() -> dict[str, Any]:
    schema = load_json("engine/schemas/cv_refinement.schema.json")
    if schema is None:  # pragma: no cover — packaged file must exist
        raise VantiaError("cv_refinement.schema.json missing", code="schema_missing")
    return schema


def _load_all() -> dict[str, Any]:
    data = load_json(_store_file())
    if not isinstance(data, dict) or not isinstance(data.get("turns"), dict):
        return {"version": 1, "turns": {}}
    return data


def _save_all(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_store_file()), exist_ok=True)
    atomic_write_json(_store_file(), data)


def turns_for(cv_improvement_id: str) -> list[dict[str, Any]]:
    """All turns for one improvement, ordered by ``turn_index``."""
    raw = _load_all()["turns"].get(cv_improvement_id, [])
    return sorted(raw, key=lambda t: t["turn_index"])


def _render_prompt(
    original_resume: str,
    current_cv: str,
    history: list[dict[str, Any]],
    user_message: str,
) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", "v1_chat_refine.md")
    with open(path, encoding="utf-8") as handle:
        template = handle.read()
    history_json = json.dumps(
        [
            {"user": t.get("user_message", ""), "assistant": t.get("change_summary", "")}
            for t in history
        ],
        ensure_ascii=False,
    )
    return (
        template.replace("{{ original_resume }}", original_resume[:12000])
        .replace("{{ current_cv }}", current_cv[:12000])
        .replace("{{ conversation_history_json }}", history_json)
        .replace("{{ user_message }}", user_message[:2000])
    )


def _try_llm(
    original_resume: str,
    current_cv: str,
    history: list[dict[str, Any]],
    user_message: str,
    *,
    run_id: str,
) -> dict[str, Any] | None:
    """One router call; returns the validated payload or None (offline/invalid)."""
    try:
        from ..llm import LLMClient, build_envelope  # noqa: F401 — import anchor
        from ..llm.client import is_dry_run
        from ..llm.router import pick
    except ImportError:  # pragma: no cover — llm package always ships
        return None
    if is_dry_run(None):
        return None
    try:
        providers = pick("chat_refine")
        chain = [(provider, provider.default_model) for provider in providers]
        client = LLMClient()
        rendered = _render_prompt(original_resume, current_cv, history, user_message)
        result = client.run_chain(
            chain,
            [{"role": "user", "content": rendered}],
            system=(
                "You are a deterministic CV refinement assistant. Output only "
                "JSON matching the schema: status, revised_cv, change_summary."
            ),
            temperature=0.0,
            run_id=run_id,
        )
        payload = json.loads(result.text)
    except Exception as exc:  # noqa: BLE001 — any provider/parse failure → honest miss
        LOGGER.info("chat_refine LLM unavailable: %s", exc)
        return None
    if validate(payload, _schema()):
        return None
    return payload


def refine(
    cv_improvement_id: str,
    user_message: str,
    user_id: str,
    *,
    original_resume: str = "",
    improved_text: str = "",
    run_id: str = "0",
) -> dict[str, Any]:
    """One refinement turn (task 15.6). See module docstring for the contract."""
    if not user_message.strip():
        raise VantiaError("user_message is required", code="message_required")
    if not cv_improvement_id:
        raise VantiaError("cv_improvement_id is required", code="improvement_id_required")

    ledger = default_ledger()
    tier = tier_of(ledger, user_id)
    limit = TURN_LIMITS.get(tier, TURN_LIMITS["free"])
    ensure_allowance(ledger, user_id)

    with _store_lock:
        history = turns_for(cv_improvement_id)
        if len(history) >= limit:
            raise TurnLimitExceeded(tier, limit)
        if ledger.balance(user_id) < REFINE_COST:
            raise InsufficientCredits(ledger.balance(user_id), REFINE_COST)

        current_cv = history[-1]["revised_text"] if history else improved_text
        payload = _try_llm(
            original_resume,
            current_cv,
            history,
            user_message,
            run_id=run_id,
        )
        if payload is None:
            # Honest refusal: no turn recorded, no credits moved (R18).
            return {
                "status": "incomplete",
                "missing": ["llm_unavailable"],
                "turns_used": len(history),
                "turns_limit": limit if limit < 10**9 else None,
                "cost_charged": 0,
            }

        turn_index = len(history) + 1
        turn = {
            "turn_index": turn_index,
            "user_message": user_message[:2000],
            "assistant_message": payload.get("change_summary", "")[:300],
            "revised_text": payload.get("revised_cv", ""),
            "change_summary": payload.get("change_summary", "")[:300],
            "created_at": utc_now(),
        }
        data = _load_all()
        data["turns"].setdefault(cv_improvement_id, []).append(turn)
        _save_all(data)

    entry = ledger.spend(
        user_id,
        REFINE_COST,
        ref=f"chat_refine:{cv_improvement_id}:{turn_index}",
        meta={"feature": "chat_refine", "turn_index": turn_index},
    )
    remaining = None if limit >= 10**9 else limit - turn_index
    return {
        **payload,
        "turn_index": turn_index,
        "turns_used": turn_index,
        "turns_limit": remaining,
        "cost_charged": abs(int(entry["amount"])),
    }


def _prompt_version() -> str:  # pragma: no cover — introspection helper
    return hashlib.sha256(PROMPT_VERSION.encode()).hexdigest()[:8]
