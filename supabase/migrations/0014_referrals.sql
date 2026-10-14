-- Migration 0014: referral program (task 15.11 §15.1).
-- Additive only: one new column on profiles + one new table + RLS policies.

ALTER TABLE profiles ADD COLUMN IF NOT EXISTS referral_code text UNIQUE;
CREATE INDEX IF NOT EXISTS idx_profiles_referral_code ON profiles (referral_code);

CREATE TABLE IF NOT EXISTS referrals (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  referrer_id     uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  referee_email   text NOT NULL,
  referee_id      uuid REFERENCES profiles(id) ON DELETE SET NULL,
  code            text,
  status          text NOT NULL DEFAULT 'pending',
  credited_at     timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT referrals_status_check CHECK (status IN ('pending','completed','expired'))
);

CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals (referrer_id, created_at DESC);

ALTER TABLE referrals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_read_own_referrals" ON referrals;
CREATE POLICY "users_read_own_referrals" ON referrals
  FOR SELECT TO authenticated USING (referrer_id = auth.uid());

DROP POLICY IF EXISTS "service_role_all_referrals" ON referrals;
CREATE POLICY "service_role_all_referrals" ON referrals
  FOR ALL TO service_role USING (true) WITH CHECK (true);
