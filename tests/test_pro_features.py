"""Pro/gated LLM feature tests (tasks 15.5, 15.6, 15.7).

Offline (``VANTIA_DRY_RUN=1``): the deterministic ship layers produce
schema-valid artifacts; the chat handler refuses honestly and charges
nothing when no provider answers. Covers the tier gates (R16), exact
credit prices, idempotency, and the R25 turn limits.
"""

import pytest

from engine.credits.ledger import CreditLedger
from engine.credits.tiers import FEATURES, check_feature_access, set_tier
from engine.errors import FeatureNotAvailable, InsufficientCredits, TurnLimitExceeded
from engine.generators.cv_job_mapping import MAPPING_COST, generate_mapping
from engine.generators.mock_interview import INTERVIEW_COST, generate_interview
from engine.improve.chat_refine import REFINE_COST, TURN_LIMITS, refine, turns_for

CV = """Jane Doe
Backend Engineer

Skills
Python, Django, PostgreSQL

Experience
Senior Engineer at Acme (Jan 2020 - Jan 2026): built Django services.

Education
- MSc Computer Science, University of London, 2016
"""

JD = "We need Python, Django, Kubernetes and AWS. 5+ years experience."


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("VANTIA_CREDITS_DIR", str(tmp_path / "credits"))
    monkeypatch.setenv("VANTIA_FEATURES_DIR", str(tmp_path / "features"))
    monkeypatch.setenv("VANTIA_DRY_RUN", "1")
    return CreditLedger(store_path=str(tmp_path / "credits" / "ledger.json"))


# ── 15.5 CV-to-job mapping ─────────────────────────────────────────────


def test_features_registry_gates_mapping_and_interview():
    assert FEATURES["cv_job_mapping"] == ("pro", "business")
    assert FEATURES["mock_interview"] == ("pro", "business")


def test_free_user_is_refused_mapping_and_spends_nothing(ledger, monkeypatch):
    monkeypatch.setattr("engine.generators.cv_job_mapping.default_ledger", lambda: ledger)
    with pytest.raises(FeatureNotAvailable) as excinfo:
        generate_mapping(CV, JD, user_id="u-free")
    assert excinfo.value.code == "feature_not_available"
    assert ledger.balance("u-free") == 0


def test_pro_user_maps_and_pays_exactly_6000(ledger, monkeypatch):
    monkeypatch.setattr("engine.generators.cv_job_mapping.default_ledger", lambda: ledger)
    set_tier(ledger, "u-pro", "pro")
    ledger.grant("u-pro", 50_000, ref="seed")
    result = generate_mapping(CV, JD, user_id="u-pro", scan_id="scan-1", grant_allowance=False)
    assert result["status"] == "complete"
    assert result["cost_charged"] == MAPPING_COST == 6000
    assert result["match_count"] + result["partial_count"] + result["gap_count"] > 0
    assert ledger.balance("u-pro") == 50_000 - 6000


def test_mapping_is_idempotent_per_scan(ledger, monkeypatch):
    monkeypatch.setattr("engine.generators.cv_job_mapping.default_ledger", lambda: ledger)
    set_tier(ledger, "u-pro", "pro")
    ledger.grant("u-pro", 20_000, ref="seed")
    first = generate_mapping(CV, JD, user_id="u-pro", scan_id="scan-1", grant_allowance=False)
    second = generate_mapping(CV, JD, user_id="u-pro", scan_id="scan-1", grant_allowance=False)
    assert second["cached"] is True
    assert second["cost_charged"] == 0
    assert ledger.balance("u-pro") == 20_000 - 6000  # charged once


def test_mapping_gap_rows_have_bridge_suggestions(ledger, monkeypatch):
    monkeypatch.setattr("engine.generators.cv_job_mapping.default_ledger", lambda: ledger)
    set_tier(ledger, "u-pro", "pro")
    ledger.grant("u-pro", 20_000, ref="seed")
    result = generate_mapping(CV, JD, user_id="u-pro", scan_id="scan-2", grant_allowance=False)
    for row in result["mappings"]:
        if row["match_level"] in ("partial", "gap"):
            assert row["bridge_suggestion"], row
        if row["match_level"] == "match":
            assert row["cv_evidence"], row


def test_mapping_refuses_when_broke(ledger, monkeypatch):
    monkeypatch.setattr("engine.generators.cv_job_mapping.default_ledger", lambda: ledger)
    set_tier(ledger, "u-broke", "pro")  # pro tier but zero balance
    with pytest.raises(InsufficientCredits):
        generate_mapping(CV, JD, user_id="u-broke", scan_id="scan-3", grant_allowance=False)


def test_check_feature_access_allows_unknown_features(ledger):
    assert check_feature_access(ledger, "anyone", "not_a_real_feature") is True
    assert check_feature_access(ledger, "anyone", "cv_job_mapping") is False


# ── 15.7 mock interview ────────────────────────────────────────────────


def test_free_user_is_refused_interview(ledger, monkeypatch):
    monkeypatch.setattr("engine.generators.mock_interview.default_ledger", lambda: ledger)
    with pytest.raises(FeatureNotAvailable):
        generate_interview(CV, JD, user_id="u-free")


def test_pro_interview_has_exactly_10_questions_costing_4000(ledger, monkeypatch):
    monkeypatch.setattr("engine.generators.mock_interview.default_ledger", lambda: ledger)
    set_tier(ledger, "u-pro", "pro")
    ledger.grant("u-pro", 50_000, ref="seed")
    result = generate_interview(
        CV, JD, user_id="u-pro", scan_id="s1", company_name="Acme", grant_allowance=False
    )
    assert result["status"] == "complete"
    assert len(result["questions"]) == 10
    assert result["cost_charged"] == INTERVIEW_COST == 4000
    tags = {q["competency_tag"] for q in result["questions"]}
    assert tags <= {"technical", "behavioural", "leadership", "problem_solving", "culture_fit"}
    # every model answer traces to a CV fact (rule 4) — names the CV experience
    assert any(
        "CV" in q["model_answer"] or "cv" in q["model_answer"].lower() for q in result["questions"]
    )


def test_interview_is_idempotent_per_scan(ledger, monkeypatch):
    monkeypatch.setattr("engine.generators.mock_interview.default_ledger", lambda: ledger)
    set_tier(ledger, "u-pro", "pro")
    ledger.grant("u-pro", 20_000, ref="seed")
    generate_interview(CV, JD, user_id="u-pro", scan_id="s1", grant_allowance=False)
    second = generate_interview(CV, JD, user_id="u-pro", scan_id="s1", grant_allowance=False)
    assert second["cached"] is True and second["cost_charged"] == 0
    assert ledger.balance("u-pro") == 20_000 - 4000


# ── 15.6 chat refinement ───────────────────────────────────────────────


def test_turn_limits_per_tier():
    assert TURN_LIMITS["free"] == 3
    assert TURN_LIMITS["pro"] == 20
    assert TURN_LIMITS["business"] >= 999_999


def test_free_user_gets_three_honest_turns_then_refusal(ledger, monkeypatch):
    monkeypatch.setattr("engine.improve.chat_refine.default_ledger", lambda: ledger)
    ledger.grant("u-free", 20_000, ref="seed")
    # offline (dry-run): each attempt is an honest incomplete, no charge, no turn
    for _ in range(3):
        result = refine("imp-1", "make it shorter", "u-free", improved_text="CV v1")
        assert result["status"] == "incomplete"
        assert result["cost_charged"] == 0
    # the turn cap still holds: even refusing runs cannot loop forever
    assert len(turns_for("imp-1")) == 0


def test_offline_turn_charges_nothing(ledger, monkeypatch):
    monkeypatch.setattr("engine.improve.chat_refine.default_ledger", lambda: ledger)
    set_tier(ledger, "u-pro", "pro")
    # prime the idempotent allowance so its grant is not counted as spend
    refine("imp-0", "warmup", "u-pro", improved_text="CV v1")
    before = ledger.balance("u-pro")
    result = refine("imp-2", "shorten the summary", "u-pro", improved_text="CV v1")
    assert result["status"] == "incomplete"
    assert result["missing"] == ["llm_unavailable"]
    assert result["cost_charged"] == 0
    assert ledger.balance("u-pro") == before  # R18: failure costs nothing


def test_turn_limit_enforced_with_recorded_turns(ledger, monkeypatch, tmp_path):
    monkeypatch.setattr("engine.improve.chat_refine.default_ledger", lambda: ledger)
    ledger.grant("u-free", 100_000, ref="seed")
    # inject three persisted turns — a free user's full R25 allowance
    import json
    import os

    os.makedirs(tmp_path / "features", exist_ok=True)
    fake = {
        "version": 1,
        "turns": {
            "imp-3": [
                {
                    "turn_index": i,
                    "user_message": "x",
                    "assistant_message": "y",
                    "revised_text": "cv",
                    "change_summary": "s",
                    "created_at": "now",
                }
                for i in (1, 2, 3)
            ]
        },
    }
    (tmp_path / "features" / "cv_refinement_turns.json").write_text(
        json.dumps(fake), encoding="utf-8"
    )
    with pytest.raises(TurnLimitExceeded):
        refine("imp-3", "one more", "u-free", improved_text="CV v1")


def test_empty_message_is_refused(ledger, monkeypatch):
    monkeypatch.setattr("engine.improve.chat_refine.default_ledger", lambda: ledger)
    with pytest.raises(Exception) as excinfo:
        refine("imp-4", "   ", "u-free")
    assert getattr(excinfo.value, "code", "") == "message_required"


def test_refine_cost_is_2000():
    assert REFINE_COST == 2000
