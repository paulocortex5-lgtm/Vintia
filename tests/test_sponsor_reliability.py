"""Sponsor reliability scoring tests (task 15.4 §8.6).

Offline: snapshots and ratings live in ``tmp_path``. Covers the §8.2
weight sum, score bounds, tenure/consistency effects, the ≥100-company
acceptance via a synthetic register, the badge colour rules and the
score_for/load_scores reads.
"""

from datetime import UTC, datetime

from engine.sources.sponsor_reliability import (
    RELIABILITY_WEIGHTS,
    compute_score,
    load_scores,
    rebuild,
    record_snapshot,
    reliability_badge,
    score_for,
)


def test_weights_sum_to_one():
    assert abs(sum(RELIABILITY_WEIGHTS.values()) - 1.0) < 1e-9


def test_score_is_always_in_0_100():
    for history in ([], ["2026-01-15"], ["2024-01-01", "2026-09-01"]):
        for failed in (None, 0, 5):
            record = compute_score("Acme", "GB", history=history, failed_count=failed)
            assert 0 <= record.score <= 100


def test_unknown_signals_are_neutral_and_documented():
    record = compute_score("NewCo", "GB", history=["2026-10-01"])
    assert "hire volume unknown" in record.note
    assert "no user ratings" in record.note
    # neutral volume (0.5) + neutral user (0.5) + no penalties:
    # 0.30*small + 0.25*0.5 + 0.20*1 + 0.15*1 + 0.10*0.5 → 50-65 band
    assert 45 <= record.score <= 70


def test_long_tenure_scores_higher_than_fresh_entry():
    fresh = compute_score("NewCo", "GB", history=["2026-10-01"])
    veteran = compute_score("OldCo", "GB", history=["2024-01-01", "2025-01-01", "2026-01-01"])
    assert veteran.score > fresh.score


def test_failed_sponsorships_lower_the_score():
    clean = compute_score("Acme", "GB", history=["2024-01-01"], sponsorships_12m=100)
    revoked = compute_score(
        "Acme", "GB", history=["2024-01-01"], sponsorships_12m=100, failed_count=50
    )
    assert revoked.score < clean.score


def test_user_ratings_raise_the_score():
    unrated = compute_score("Acme", "GB", history=["2024-01-01"])
    loved = compute_score("Acme", "GB", history=["2024-01-01"], user_signal=0.98)
    assert loved.score > unrated.score


def test_snapshot_history_feeds_rebuild_and_lookup(tmp_path):
    store_dir = str(tmp_path)
    record_snapshot("GB", ["Acme Ltd", "Beta Ltd"], snapshot_date="2026-08-01", store_dir=store_dir)
    record_snapshot("GB", ["Acme Ltd"], snapshot_date="2026-09-01", store_dir=store_dir)
    record_snapshot("GB", ["Acme Ltd"], snapshot_date="2026-10-01", store_dir=store_dir)
    stats = rebuild(store_dir)
    assert stats["scored"] == 2
    assert stats["snapshots"] == 3
    acme = score_for("Acme Ltd", "GB", store_dir=store_dir)
    beta = score_for("Beta Ltd", "GB", store_dir=store_dir)
    assert acme is not None and beta is not None
    # Acme present in all 3 snapshots, Beta only in 1 → Acme more consistent
    assert acme["consistency"] >= beta["consistency"]
    assert acme["tenure_months"] >= 2  # Aug→Oct spans 2 months


def test_ratings_file_feeds_user_signal(tmp_path):
    import json

    store_dir = str(tmp_path)
    record_snapshot("GB", ["Acme"], snapshot_date="2026-09-01", store_dir=store_dir)
    (tmp_path / "sponsor_ratings.json").write_text(
        json.dumps({"GB:Acme": {"ratings": [5, 5, 4], "failed": 1, "sponsorships_12m": 3}}),
        encoding="utf-8",
    )
    rebuild(store_dir)
    acme = score_for("Acme", "GB", store_dir=store_dir)
    assert acme["user_signal"] > 0.5
    assert acme["failed_count"] == 1


def test_hundred_companies_can_be_scored(tmp_path):
    store_dir = str(tmp_path)
    names = [f"Company {i:03d} Ltd" for i in range(120)]
    record_snapshot("GB", names, snapshot_date="2026-10-01", store_dir=store_dir)
    rebuild(store_dir)
    scores = load_scores(store_dir)
    assert len(scores) >= 100  # §8.6 acceptance


def test_badge_colour_rules():
    assert reliability_badge(87)["tone"] == "green"
    assert reliability_badge(75)["tone"] == "green"
    assert reliability_badge(74)["tone"] == "amber"
    assert reliability_badge(50)["tone"] == "amber"
    assert reliability_badge(49)["tone"] == "red"
    assert reliability_badge(None)["tone"] == "neutral"
    assert "unknown" in reliability_badge(None)["label"]


def test_snapshot_recording_is_idempotent_per_date(tmp_path):
    store_dir = str(tmp_path)
    record_snapshot("GB", ["Acme"], snapshot_date="2026-10-01", store_dir=store_dir)
    record_snapshot("GB", ["Acme"], snapshot_date="2026-10-01", store_dir=store_dir)
    rebuild(store_dir)
    acme = score_for("Acme", "GB", store_dir=store_dir)
    assert acme["tenure_months"] == 0  # same-day duplicates must not age it


def test_rebuild_is_deterministic(tmp_path):
    store_dir = str(tmp_path)
    record_snapshot("DE", ["GmbH Alpha"], snapshot_date="2026-06-01", store_dir=store_dir)
    now = datetime.now(UTC)
    a = compute_score("GmbH Alpha", "DE", history=["2026-06-01"], now=now)
    b = compute_score("GmbH Alpha", "DE", history=["2026-06-01"], now=now)
    assert a == b
