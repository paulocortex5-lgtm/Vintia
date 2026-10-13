-- Migration 0013: job alert subscriptions (task 15.9 §13.1).
-- Additive only: one new table + RLS policies.

CREATE TABLE IF NOT EXISTS job_alerts (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  filters       jsonb NOT NULL DEFAULT '{}',
  frequency     text NOT NULL DEFAULT 'daily',
  last_sent_at  timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT job_alerts_freq_check CHECK (frequency IN ('daily','weekly'))
);

CREATE INDEX IF NOT EXISTS idx_job_alerts_user ON job_alerts (user_id, created_at DESC);

ALTER TABLE job_alerts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_rw_own_alerts" ON job_alerts;
CREATE POLICY "users_rw_own_alerts" ON job_alerts
  FOR ALL TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "service_role_all_alerts" ON job_alerts;
CREATE POLICY "service_role_all_alerts" ON job_alerts
  FOR ALL TO service_role USING (true) WITH CHECK (true);
