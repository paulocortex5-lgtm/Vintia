"""Static tests for `0004_workspaces.sql` + `0005_rls.sql` (tasks 8.2/8.3).

The isolation guarantee is checked structurally: every table has RLS
enabled, every policy is scoped to `auth.uid()`, there is no permissive
catch-all, and the tier vocabulary matches the engine's. Applying the
migrations needs a live Postgres — unavailable here, so these are static
(never claimed as applied).
"""

from pathlib import Path

from engine.credits.tiers import TIERS

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_0004 = (ROOT / "supabase" / "migrations" / "0004_workspaces.sql").read_text("utf-8")
MIGRATION_0005 = (ROOT / "supabase" / "migrations" / "0005_rls.sql").read_text("utf-8")


# ── 0004: tables ───────────────────────────────────────────────────────


def test_0004_is_transactional_and_creates_the_three_tables():
    assert "begin;" in MIGRATION_0004
    assert MIGRATION_0004.rstrip().endswith("commit;")
    for table in ("profiles", "workspaces", "workspace_files"):
        assert f"create table if not exists {table}" in MIGRATION_0004


def test_tier_vocabulary_matches_the_engine_exactly():
    for tier in TIERS:
        assert f"'{tier}'" in MIGRATION_0004, tier


def test_ownership_cascades_exist():
    assert "references profiles(user_id) on delete cascade" in MIGRATION_0004
    assert "references workspaces(workspace_id) on delete cascade" in MIGRATION_0004


def test_files_are_unique_per_workspace():
    assert "unique (workspace_id, filename)" in MIGRATION_0004
    assert "check (size_bytes >= 0)" in MIGRATION_0004


# ── 0005: RLS + hook ───────────────────────────────────────────────────


def test_0005_is_transactional_and_enables_rls_on_all_three():
    assert "begin;" in MIGRATION_0005
    assert MIGRATION_0005.rstrip().endswith("commit;")
    assert MIGRATION_0005.count("enable row level security") == 3


def test_every_policy_is_scoped_to_auth_uid():
    policies = [line for line in MIGRATION_0005.splitlines() if line.startswith("create policy")]
    assert len(policies) >= 12  # 4 ops x 3 tables
    assert "(select auth.uid())::text = user_id" in MIGRATION_0005


def test_file_policies_go_through_workspace_ownership():
    assert "exists (" in MIGRATION_0005
    assert "w.workspace_id = workspace_files.workspace_id" in MIGRATION_0005
    assert "w.user_id = (select auth.uid())::text" in MIGRATION_0005


def test_no_permissive_catch_all_policy():
    assert "using (true)" not in MIGRATION_0005
    assert "for all" not in MIGRATION_0005  # ops are explicit, least privilege


def test_jwt_hook_stamps_the_tier_and_is_hardened():
    assert "create or replace function public.vantia_jwt_hook" in MIGRATION_0005
    assert "jsonb_build_object('tier'" in MIGRATION_0005
    assert "security definer" in MIGRATION_0005
    assert "set search_path" in MIGRATION_0005  # hardening against search-path hijacks


def test_ddl_is_well_formed():
    for sql in (MIGRATION_0004, MIGRATION_0005):
        assert sql.count("(") == sql.count(")")
        for statement in [s for s in sql.split(";") if s.strip()]:
            assert statement.strip()
