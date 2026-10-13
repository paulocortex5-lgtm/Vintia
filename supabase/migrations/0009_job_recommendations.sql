-- Migration 0009: job recommendations cache (task 15.1 §5.3).
-- Additive only: one new table + index + RLS policies.

CREATE TABLE IF NOT EXISTS job_recommendations (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id      uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  cv_file_id        uuid REFERENCES workspace_files(id) ON DELETE SET NULL,
  filters           jsonb NOT NULL DEFAULT '{}',
  recommended_jobs  jsonb NOT NULL,
  created_at        timestamptz NOT NULL DEFAULT now(),
  expires_at        timestamptz NOT NULL DEFAULT (now() + interval '24 hours')
);

CREATE INDEX IF NOT EXISTS idx_job_recs_workspace
  ON job_recommendations (workspace_id, created_at DESC);

ALTER TABLE job_recommendations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_rw_own_job_recs" ON job_recommendations;
CREATE POLICY "users_rw_own_job_recs" ON job_recommendations
  FOR ALL TO authenticated
  USING (workspace_id IN (SELECT id FROM workspaces WHERE user_id = auth.uid()))
  WITH CHECK (workspace_id IN (SELECT id FROM workspaces WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "service_role_all_job_recs" ON job_recommendations;
CREATE POLICY "service_role_all_job_recs" ON job_recommendations
  FOR ALL TO service_role USING (true) WITH CHECK (true);
