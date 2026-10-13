-- Migration 0012: application tracker (task 15.8 §12.1).
-- Additive only: one new table + index + RLS policies.

CREATE TABLE IF NOT EXISTS applications (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id  uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  job_id        text NOT NULL,
  job_snapshot  jsonb NOT NULL,
  status        text NOT NULL DEFAULT 'applied',
  notes         text,
  applied_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT applications_status_check
    CHECK (status IN ('applied','interview','offer','rejected','withdrawn'))
);

CREATE INDEX IF NOT EXISTS idx_applications_workspace
  ON applications (workspace_id, updated_at DESC);

ALTER TABLE applications ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_rw_own_applications" ON applications;
CREATE POLICY "users_rw_own_applications" ON applications
  FOR ALL TO authenticated
  USING (workspace_id IN (SELECT id FROM workspaces WHERE user_id = auth.uid()))
  WITH CHECK (workspace_id IN (SELECT id FROM workspaces WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "service_role_all_applications" ON applications;
CREATE POLICY "service_role_all_applications" ON applications
  FOR ALL TO service_role USING (true) WITH CHECK (true);
