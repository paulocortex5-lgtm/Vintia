-- Migration 0015: public API keys for universities (task 15.12 §16.1).
-- Additive only: one new table. Keys are stored hashed (SHA-256), never raw.

CREATE TABLE IF NOT EXISTS api_keys (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  key_hash            text NOT NULL UNIQUE,
  owner_email         text NOT NULL,
  name                text,
  tier                text NOT NULL DEFAULT 'free',
  rate_limit_per_min  int NOT NULL DEFAULT 10,
  created_at          timestamptz NOT NULL DEFAULT now(),
  last_used_at        timestamptz
);

CREATE INDEX IF NOT EXISTS idx_api_keys_owner ON api_keys (owner_email, created_at DESC);

-- Service-role only: keys are managed by the admin API, never by end users,
-- so no authenticated RLS policy is added (fail-closed by default).
