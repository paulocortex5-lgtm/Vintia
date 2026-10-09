"""Credit ledger tests (task 11.1) — append-only, idempotent, R46.

Every movement is verified against the file on disk: the ledger is the
authoritative store, the Supabase mirror is write-through, and a replayed
ref must never move money twice.
"""

import json
import threading

import pytest

from engine.credits.ledger import (
    CreditLedger,
    default_ledger,
    reset_default_ledger,
    topup_from_paddle,
)
from engine.errors import InsufficientCredits, PaddleError, VantiaError


@pytest.fixture()
def ledger(tmp_path):
    return CreditLedger(store_path=str(tmp_path / "ledger.json"))


# ── Lifecycle ──────────────────────────────────────────────────────────


def test_unknown_user_has_zero_balance_not_credits(ledger):
    assert ledger.balance("nobody") == 0
    assert ledger.entries("nobody") == []


def test_topup_spend_refund_lifecycle(ledger):
    ledger.topup("u1", 10_000, "paddle:evt1")
    assert ledger.balance("u1") == 10_000
    entry = ledger.spend("u1", 2_000, "cv_scan:run1", meta={"operation": "cv_scan"})
    assert entry["balance_after"] == 8_000
    assert ledger.balance("u1") == 8_000
    ledger.refund("u1", 2_000, "cv_scan:run1:refund")
    assert ledger.balance("u1") == 10_000


def test_entries_are_append_only_with_balance_after_chain(ledger):
    ledger.grant("u1", 10_000, "allowance:u1:2026-10")
    ledger.spend("u1", 2_000, "a")
    ledger.spend("u1", 500, "b")
    rows = ledger.entries("u1")
    assert [e["kind"] for e in rows] == ["grant", "spend", "spend"]
    assert [e["balance_after"] for e in rows] == [10_000, 8_000, 7_500]
    # append-only: amounts sum to the balance
    assert sum(e["amount"] for e in rows) == ledger.balance("u1") == 7_500


def test_summary_totals_match_the_entries(ledger):
    ledger.topup("u1", 10_000, "t1")
    ledger.spend("u1", 2_500, "s1")
    summary = ledger.summary("u1")
    assert summary["balance"] == 7_500
    assert summary["entry_count"] == 2
    assert summary["total_earned"] == 10_000
    assert summary["total_spent"] == 2_500
    assert summary["last_entry_ts"]


def test_entries_limit_returns_the_newest(ledger):
    for i in range(5):
        ledger.topup("u1", 1, f"t{i}")
    assert [e["ref"] for e in ledger.entries("u1", limit=2)] == ["t3", "t4"]
    assert ledger.entries("u1", limit=0) == []


# ── Idempotency (R50-style) ────────────────────────────────────────────


def test_same_ref_never_moves_money_twice(ledger):
    first = ledger.topup("u1", 10_000, "paddle:evt_same")
    replay = ledger.topup("u1", 10_000, "paddle:evt_same")
    assert replay == first
    assert ledger.balance("u1") == 10_000
    assert len(ledger.entries("u1")) == 1

    ledger.spend("u1", 500, "scan:fixed-ref")
    ledger.spend("u1", 500, "scan:fixed-ref")  # replay: no second deduction
    assert ledger.balance("u1") == 9_500
    assert len(ledger.entries("u1")) == 2


def test_find_ref_reports_applications(ledger):
    assert ledger.find_ref("u1", "nope") is None
    ledger.grant("u1", 100, "g1")
    assert ledger.find_ref("u1", "g1")["amount"] == 100


# ── R46 / invalid input ────────────────────────────────────────────────


def test_insufficient_credits_raises_and_writes_nothing(ledger):
    ledger.topup("u1", 1_000, "t")
    with pytest.raises(InsufficientCredits) as excinfo:
        ledger.spend("u1", 5_000, "too-expensive")
    assert excinfo.value.code == "insufficient_credits"
    assert excinfo.value.context["balance"] == 1_000
    assert excinfo.value.context["required"] == 5_000
    assert ledger.balance("u1") == 1_000  # nothing was written
    assert [e["ref"] for e in ledger.entries("u1")] == ["t"]


def test_negative_or_empty_inputs_refuse(ledger):
    with pytest.raises(VantiaError) as e1:
        ledger.apply("", 100, kind="topup", ref="r")
    assert e1.value.code == "user_id_required"
    with pytest.raises(VantiaError) as e2:
        ledger.apply("u1", 100, kind="miracle", ref="r")
    assert e2.value.code == "ledger_kind_invalid"
    with pytest.raises(VantiaError) as e3:
        ledger.apply("u1", 100, kind="topup", ref="")
    assert e3.value.code == "ledger_ref_required"
    with pytest.raises(VantiaError) as e4:
        ledger.apply("u1", 0, kind="topup", ref="r")
    assert e4.value.code == "ledger_amount_invalid"
    with pytest.raises(VantiaError) as e5:
        ledger.topup("u1", -5, "r")
    assert e5.value.code == "ledger_amount_invalid"
    with pytest.raises(VantiaError) as e6:
        ledger.spend("u1", -5, "r")
    assert e6.value.code == "ledger_amount_invalid"
    assert ledger.balance("u1") == 0


# ── Persistence ────────────────────────────────────────────────────────


def test_balance_round_trips_through_a_new_instance(tmp_path):
    path = str(tmp_path / "ledger.json")
    CreditLedger(store_path=path).topup("u1", 7_000, "t")
    fresh = CreditLedger(store_path=path)
    assert fresh.balance("u1") == 7_000
    assert fresh.tier_of("u1") == "free"
    fresh.set_tier("u1", "pro")
    assert CreditLedger(store_path=path).tier_of("u1") == "pro"


def test_corrupt_store_fails_loudly_instead_of_erasing_balances(tmp_path):
    """A damaged ledger must never be silently reset — money would vanish."""
    path = tmp_path / "ledger.json"
    path.write_text("{not json", encoding="utf-8")
    ledger = CreditLedger(store_path=str(path))
    with pytest.raises(VantiaError) as excinfo:
        ledger.balance("u1")
    assert excinfo.value.code == "ledger_corrupt"

    path.write_text('["still", "not", "a", "ledger"]', encoding="utf-8")
    with pytest.raises(VantiaError) as excinfo2:
        ledger.topup("u1", 100, "t")
    assert excinfo2.value.code == "ledger_corrupt"
    # an absent file, by contrast, starts fresh
    other = CreditLedger(store_path=str(tmp_path / "fresh.json"))
    other.topup("u1", 100, "t")
    assert other.balance("u1") == 100


def test_persisted_file_is_valid_json_with_provenance(ledger):
    ledger.grant("u1", 10_000, "allowance:u1:2026-10", meta={"tier": "free"})
    with open(ledger.path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["version"] == 1
    entry = data["users"]["u1"]["entries"][0]
    assert entry["meta"]["tier"] == "free"
    assert entry["balance_after"] == 10_000


# ── Mirror (STEP K: write-through, never raises) ───────────────────────


class _FakeSupabase:
    def __init__(self, explode: bool = False) -> None:
        self.rows: dict[str, list[dict]] = {}
        self.explode = explode

    def upsert(self, table, rows, *, service=False):
        if self.explode:
            raise RuntimeError("supabase down")
        self.rows.setdefault(table, []).extend(rows)
        return True


def test_mirror_receives_ledger_and_balance_rows(tmp_path):
    client = _FakeSupabase()
    ledger = CreditLedger(store_path=str(tmp_path / "ledger.json"), supabase_client=client)
    ledger.topup("u1", 10_000, "paddle:evt1")
    ledger.spend("u1", 2_000, "scan:1")

    assert len(client.rows["credit_ledger"]) == 2
    assert [r["user_id"] for r in client.rows["credit_ledger"]] == ["u1", "u1"]
    assert client.rows["credit_balances"][-1]["balance"] == 8_000
    # the local ledger stays authoritative and in sync
    assert CreditLedger(store_path=ledger.path).balance("u1") == 8_000


def test_mirror_failure_never_breaks_a_movement(tmp_path):
    path = str(tmp_path / "ledger.json")
    exploding = CreditLedger(store_path=path, supabase_client=_FakeSupabase(explode=True))
    exploding.topup("u1", 500, "t")  # must not raise
    assert CreditLedger(store_path=path).balance("u1") == 500


# ── Default singleton + Paddle contract ────────────────────────────────


def test_default_ledger_honours_the_env_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_CREDITS_DIR", str(tmp_path))
    reset_default_ledger()
    try:
        default_ledger().topup("u1", 10, "t")
        assert (tmp_path / "ledger.json").exists()
    finally:
        reset_default_ledger()


def test_topup_from_paddle_is_idempotent_by_event(tmp_path):
    ledger = CreditLedger(store_path=str(tmp_path / "ledger.json"))
    topup_from_paddle("u1", 10_000, "evt_1", ledger=ledger)
    topup_from_paddle("u1", 10_000, "evt_1", ledger=ledger)
    assert ledger.balance("u1") == 10_000
    rows = ledger.entries("u1")
    assert len(rows) == 1 and rows[0]["ref"] == "paddle:evt_1"
    assert rows[0]["meta"]["source"] == "paddle"


def test_topup_from_paddle_wraps_storage_failures(tmp_path, monkeypatch):
    ledger = CreditLedger(store_path=str(tmp_path / "ledger.json"))

    def _boom(self, data):
        raise OSError("disk full")

    monkeypatch.setattr(CreditLedger, "_save", _boom)
    with pytest.raises(PaddleError, match="ledger unavailable"):
        topup_from_paddle("u1", 10_000, "evt_fail", ledger=ledger)


# ── Concurrency ────────────────────────────────────────────────────────


def test_concurrent_distinct_refs_all_land(ledger):
    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            ledger.topup("u1", 100, f"t{i}")
        except Exception as exc:  # noqa: BLE001 — collected for assertion
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert ledger.balance("u1") == 800
    assert len(ledger.entries("u1")) == 8
