-- Migration 0010: sponsor reliability scores (task 15.4 §8.3).
-- Additive only: one new table + index + RLS policies.

CREATE TABLE IF NOT EXISTS sponsor_reliability (
  company_name     text NOT NULL,
  country          char(2) NOT NULL,
  score            int NOT NULL CHECK (score BETWEEN 0 AND 100),
  tenure_months    int,
  sponsorships_12m int,
  failed_count     int,
  updated_at       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (country, company_name)
);

CREATE INDEX IF NOT EXISTS idx_sponsor_reliability_country
  ON sponsor_reliability (country, score DESC);

ALTER TABLE sponsor_reliability ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "public_read_sponsor_reliability" ON sponsor_reliability;
CREATE POLICY "public_read_sponsor_reliability" ON sponsor_reliability
  FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "service_role_all_sponsor_reliability" ON sponsor_reliability;
CREATE POLICY "service_role_all_sponsor_reliability" ON sponsor_reliability
  FOR ALL TO service_role USING (true) WITH CHECK (true);
