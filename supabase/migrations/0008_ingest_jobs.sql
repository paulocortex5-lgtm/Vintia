-- Migration 0008: job ingest tables for direct-link verification (15.2)
-- and anti-predatory enforcement (15.3).
--
-- Additive only (RULE 0.13): both tables are new, so IF NOT EXISTS guards
-- suffice. The engine's local-first JSON store mirrors these tables and
-- remains authoritative for offline runs; these tables are the production
-- backing store for search, recommendations and the status page.
--
-- The ingest.jobs FTS helper and the rejected_jobs audit are new.
-- No existing table, column, policy or data is touched.

-- ── ingest schema ─────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS ingest;

-- ── jobs: ingested postings with link-verification state ──────────────
CREATE TABLE IF NOT EXISTS ingest.jobs (
  id                text PRIMARY KEY,  -- '{portal}:{external_id}', stable across re-ingest
  portal            text NOT NULL,
  external_id       text NOT NULL,
  title             text NOT NULL,
  company           text NOT NULL,
  company_domain    text NOT NULL DEFAULT '',
  url               text NOT NULL,
  location          text NOT NULL DEFAULT '',
  country           char(2) NOT NULL DEFAULT '',
  posted_at         date,
  closes_at         date,
  description       text NOT NULL DEFAULT '',
  visa_sponsorship  boolean,
  -- task 15.2 §6.3 — direct application link verification columns
  apply_url         text NOT NULL DEFAULT '',
  apply_url_domain  text NOT NULL DEFAULT '',
  link_status       text NOT NULL DEFAULT 'unverified'
    CHECK (link_status IN ('unverified', 'verified', 'expired', 'rejected', 'stale')),
  link_checked_at   timestamptz,
  link_expires_at   timestamptz,
  link_status_reason text NOT NULL DEFAULT '',
  extra             jsonb NOT NULL DEFAULT '{}',
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jobs_country_status
  ON ingest.jobs (country, link_status, posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_link_status
  ON ingest.jobs (link_status, link_checked_at);
CREATE INDEX IF NOT EXISTS idx_jobs_apply_url_domain
  ON ingest.jobs (apply_url_domain);
CREATE INDEX IF NOT EXISTS idx_jobs_company
  ON ingest.jobs (company);

-- Jobs are public catalogue data (no per-user rows); read access for the
-- authenticated app, writes restricted to the service role.
ALTER TABLE ingest.jobs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "public_read_jobs" ON ingest.jobs;
CREATE POLICY "public_read_jobs" ON ingest.jobs
  FOR SELECT TO authenticated USING (true);
DROP POLICY IF EXISTS "service_role_all_jobs" ON ingest.jobs;
CREATE POLICY "service_role_all_jobs" ON ingest.jobs
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ── rejected_jobs: anti-predatory audit trail (task 15.3 §7.3) ────────
CREATE TABLE IF NOT EXISTS ingest.rejected_jobs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source        text NOT NULL,
  external_id   text NOT NULL,
  reason_code   text NOT NULL
    CHECK (reason_code IN (
      'fee_language', 'unverified_link', 'domain_mismatch',
      'scam_aggregator', 'injection_detected', 'pii_request'
    )),
  reason_detail text,
  payload       jsonb NOT NULL,
  rejected_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source, external_id, reason_code)
);

CREATE INDEX IF NOT EXISTS idx_rejected_reason
  ON ingest.rejected_jobs (reason_code, rejected_at DESC);

ALTER TABLE ingest.rejected_jobs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_rejected_jobs" ON ingest.rejected_jobs;
CREATE POLICY "service_role_all_rejected_jobs" ON ingest.rejected_jobs
  FOR ALL TO service_role USING (true) WITH CHECK (true);
