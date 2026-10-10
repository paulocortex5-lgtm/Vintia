-- ============================================================================
-- 0005_rls.sql — row-level security + access-token hook (task 8.3)
--
-- Isolation guarantee: a user row is visible/writable ONLY through
-- `auth.uid()` — the JWT `sub` claim Supabase Auth verifies server-side.
-- There is intentionally no "anonymous can read" policy; the engine's
-- service role bypasses RLS natively as the trusted backend.
--
-- The `vantia_jwt_hook` function stamps the user's tier into every access
-- token's claims. Registering it as a Custom Access Token Hook is a
-- dashboard action at launch (cannot be applied from here) — the function
-- ships version-controlled so the definition is reviewable and testable.
--
-- Run order: psql "$DATABASE_URL" -f supabase/migrations/0005_rls.sql
-- ============================================================================

begin;

alter table profiles enable row level security;
alter table workspaces enable row level security;
alter table workspace_files enable row level security;

-- ── profiles: own row only ─────────────────────────────────────────────
create policy "profiles_select_own" on profiles
    for select using ((select auth.uid())::text = user_id);
create policy "profiles_insert_own" on profiles
    for insert with check ((select auth.uid())::text = user_id);
create policy "profiles_update_own" on profiles
    for update using ((select auth.uid())::text = user_id)
    with check ((select auth.uid())::text = user_id);
create policy "profiles_delete_own" on profiles
    for delete using ((select auth.uid())::text = user_id);

-- ── workspaces: own rows only ──────────────────────────────────────────
create policy "workspaces_select_own" on workspaces
    for select using ((select auth.uid())::text = user_id);
create policy "workspaces_insert_own" on workspaces
    for insert with check ((select auth.uid())::text = user_id);
create policy "workspaces_update_own" on workspaces
    for update using ((select auth.uid())::text = user_id)
    with check ((select auth.uid())::text = user_id);
create policy "workspaces_delete_own" on workspaces
    for delete using ((select auth.uid())::text = user_id);

-- ── workspace_files: via ownership of the parent workspace ─────────────
create policy "workspace_files_select_own" on workspace_files
    for select using (exists (
        select 1 from workspaces w
        where w.workspace_id = workspace_files.workspace_id
          and w.user_id = (select auth.uid())::text));
create policy "workspace_files_insert_own" on workspace_files
    for insert with check (exists (
        select 1 from workspaces w
        where w.workspace_id = workspace_files.workspace_id
          and w.user_id = (select auth.uid())::text));
create policy "workspace_files_update_own" on workspace_files
    for update using (exists (
        select 1 from workspaces w
        where w.workspace_id = workspace_files.workspace_id
          and w.user_id = (select auth.uid())::text))
    with check (exists (
        select 1 from workspaces w
        where w.workspace_id = workspace_files.workspace_id
          and w.user_id = (select auth.uid())::text));
create policy "workspace_files_delete_own" on workspace_files
    for delete using (exists (
        select 1 from workspaces w
        where w.workspace_id = workspace_files.workspace_id
          and w.user_id = (select auth.uid())::text));

-- ── access-token hook: stamp the tier into every JWT ───────────────────
-- Register in Supabase Auth → Hooks → Custom Access Token Hook at launch.
create or replace function public.vantia_jwt_hook(event jsonb) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
    user_tier text;
begin
    select tier into user_tier
      from public.profiles
     where user_id = (event->>'user_id');
    event := jsonb_set(
        event,
        '{claims}',
        coalesce(event->'claims', '{}'::jsonb) || jsonb_build_object('tier', coalesce(user_tier, 'free'))
    );
    return event;
end;
$$;

commit;
