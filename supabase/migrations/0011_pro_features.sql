-- Migration 0011: Pro & gated LLM feature tables (tasks 15.5, 15.6, 15.7).
-- Additive only: three new tables + indexes + RLS policies.

-- ── CV-to-job mapping artifacts (task 15.5) ───────────────────────────
CREATE TABLE IF NOT EXISTS cv_job_mappings (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scan_id       text NOT NULL,
  workspace_id  uuid NOT NULL,
  mapping       jsonb NOT NULL,
  gaps_count    int NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cv_job_mappings_scan ON cv_job_mappings (scan_id);

ALTER TABLE cv_job_mappings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_rw_own_cv_job_mappings" ON cv_job_mappings;
CREATE POLICY "users_rw_own_cv_job_mappings" ON cv_job_mappings
  FOR ALL TO authenticated
  USING (workspace_id IN (SELECT id FROM workspaces WHERE user_id = auth.uid()))
  WITH CHECK (workspace_id IN (SELECT id FROM workspaces WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "service_role_all_cv_job_mappings" ON cv_job_mappings;
CREATE POLICY "service_role_all_cv_job_mappings" ON cv_job_mappings
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ── CV refinement turns (task 15.6) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS cv_refinement_turns (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cv_improvement_id   text NOT NULL,
  turn_index          int NOT NULL,
  user_message        text NOT NULL,
  assistant_message   text NOT NULL,
  revised_text        text,
  change_summary      text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (cv_improvement_id, turn_index)
);

ALTER TABLE cv_refinement_turns ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_all_refinements" ON cv_refinement_turns;
CREATE POLICY "service_role_all_refinements" ON cv_refinement_turns
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ── Mock interviews (task 15.7) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS mock_interviews (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scan_id       text NOT NULL,
  workspace_id  uuid NOT NULL,
  questions     jsonb NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mock_interviews_scan ON mock_interviews (scan_id);

ALTER TABLE mock_interviews ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_rw_own_mock_interviews" ON mock_interviews;
CREATE POLICY "users_rw_own_mock_interviews" ON mock_interviews
  FOR ALL TO authenticated
  USING (workspace_id IN (SELECT id FROM workspaces WHERE user_id = auth.uid()))
  WITH CHECK (workspace_id IN (SELECT id FROM workspaces WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "service_role_all_mock_interviews" ON mock_interviews;
CREATE POLICY "service_role_all_mock_interviews" ON mock_interviews
  FOR ALL TO service_role USING (true) WITH CHECK (true);
