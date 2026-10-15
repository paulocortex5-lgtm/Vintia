"""Platform chatbot — daily message rate limits by tier (task 1.1 / Part 12.4).

Tier rate limits on conversational messages per calendar day:
  free       -> 20
  pro        -> 200
  business   -> unlimited

Local-first message store (``$VANTIA_CHAT_DIR`` default ``.vantia/chat/``)
with a best-effort Supabase mirror for ``chat_conversations`` /
``chat_messages`` (see supabase/migrations/0016_chat.sql). The Supabase
tables carry RLS so the web frontend can read/write its own rows directly;
the engine writes through its service role and never raises on mirror
failure (STEP K).

When every configured LLM provider is offline the endpoint returns an honest
``incomplete`` reply instead of fabricating an answer (R18).
"""

from __future__ import annotations

import os
import threading
from datetime import UTC, datetime
from typing import Any

from .credits import default_ledger, set_tier, tier_of
from .credits.ledger import CreditLedger
from .errors import VantiaError
from .json_utils import atomic_write_json, load_json
from .logging_config import utc_now
from .persistence.supabase_client import SupabaseClient

__all__ = [
    "CHAT_RATE_LIMITS",
    "MessageRateLimitExceeded",
    "chat",
    "messages_for",
    "set_tier",
    "tier_of",
]

#: Max conversational messages per calendar day, by tier.
CHAT_RATE_LIMITS: dict[str, int] = {
    "free": 20,
    "pro": 200,
    "business": 10**9,  # effectively unlimited
}

PROMPT_VERSION = "1.0.0"

_store_lock = threading.RLock()
_supabase = SupabaseClient()  # best-effort; degrades when unconfigured


def _default_dir() -> str:
    return os.environ.get("VANTIA_CHAT_DIR", os.path.join(".vantia", "chat"))


def _store_file() -> str:
    return os.path.join(_default_dir(), "messages.json")


def _load_all() -> dict[str, Any]:
    data = load_json(_store_file())
    if not isinstance(data, dict) or not isinstance(data.get("messages"), dict):
        return {"version": 1, "messages": {}}
    return data


def _save_all(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_store_file()), exist_ok=True)
    atomic_write_json(_store_file(), data)


def messages_for(user_id: str) -> list[dict[str, Any]]:
    """All stored messages for ``user_id``, newest first."""
    with _store_lock:
        return sorted(
            _load_all()["messages"].get(user_id, []),
            key=lambda m: m.get("created_at", ""),
            reverse=True,
        )


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _render_prompt(history: list[dict[str, Any]], user_message: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", "v1_platform_chat.md")
    with open(path, encoding="utf-8") as handle:
        template = handle.read()
    history_text = "\n".join(
        f"{m.get('role', 'user')}: {m.get('content', '')}" for m in history[-10:]
    )
    return (
        template.replace("{{ conversation_history }}", history_text or "(none yet)")
        .replace("{{ user_message }}", user_message)
    )


def _call_llm(history: list[dict[str, Any]], user_message: str, *, run_id: str) -> str | None:
    """One LLM call through the router; None when no provider can answer."""
    try:
        from .llm import LLMClient
        from .llm.router import pick
    except ImportError:  # pragma: no cover — llm package always ships
        return None
    try:
        chain = pick()  # default profile (free_only)
        if not chain:
            return None
        client = LLMClient()
        rendered = _render_prompt(history, user_message)
        result = client.run_chain(
            chain,
            [{"role": "user", "content": rendered}],
            system=(
                "You are Vantia's platform assistant. Reply in plain text, "
                "concise and accurate, never inventing facts."
            ),
            temperature=0.2,
            run_id=run_id,
        )
        text = (result.text or "").strip()
        return text or None
    except Exception:  # noqa: BLE001 — honest degradation
        return None


def _mirror_to_supabase(rows: list[dict[str, Any]]) -> None:
    """Best-effort write to chat_messages; never raises (STEP K)."""
    try:
        _supabase.upsert("chat_messages", rows, service=True)
    except Exception:  # noqa: BLE001 — mirror must never break the chat path
        pass


class MessageRateLimitExceeded(VantiaError):
    """Daily conversational message cap reached for the tier."""

    code = "rate_limited"

    def __init__(self, tier: str, limit: int, used: int) -> None:
        super().__init__(
            f"daily message limit reached for the {tier} tier "
            f"({used}/{limit} messages today); upgrade for more",
            tier=tier,
            limit=limit,
            used=used,
        )


def chat(
    user_id: str,
    message: str,
    *,
    conversation_id: str = "",
    run_id: str = "0",
) -> dict[str, Any]:
    """One conversational turn (task 1.1 / Part 12.4)."""
    if not user_id:
        raise VantiaError("user_id is required", code="user_id_required")
    if not message or not message.strip():
        raise VantiaError("message is required", code="message_required")
    message = message.strip()[:4000]
    if not conversation_id:
        conversation_id = f"conv-{user_id}-{utc_now()}"

    ledger = default_ledger()
    tier = tier_of(ledger, user_id)
    limit = CHAT_RATE_LIMITS.get(tier, CHAT_RATE_LIMITS["free"])

    with _store_lock:
        history = messages_for(user_id)
        used_today = sum(
            1
            for m in history
            if m.get("role") == "user" and m.get("created_at", "").startswith(_today())
        )
        if used_today >= limit:
            raise MessageRateLimitExceeded(tier, limit, used_today)

        reply = _call_llm(history, message, run_id=run_id)
        if reply is None:
            return {
                "status": "incomplete",
                "missing": ["llm_unavailable"],
                "reply": "",
                "conversation_id": conversation_id,
                "tier": tier,
                "used_today": used_today,
                "limit": limit if limit < 10**9 else None,
            }

        now = utc_now()
        user_msg = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": "user",
            "content": message,
            "created_at": now,
        }
        assistant_msg = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": "assistant",
            "content": reply,
            "created_at": now,
        }
        store = _load_all()
        store.setdefault("messages", {}).setdefault(user_id, [])
        store["messages"][user_id].extend([user_msg, assistant_msg])
        _save_all(store)
        _mirror_to_supabase([user_msg, assistant_msg])

        return {
            "status": "ok",
            "reply": reply,
            "conversation_id": conversation_id,
            "tier": tier,
            "used_today": used_today + 1,
            "limit": limit if limit < 10**9 else None,
        }

