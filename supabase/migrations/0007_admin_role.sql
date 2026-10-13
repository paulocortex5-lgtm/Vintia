-- ============================================================================
-- 0007_admin_role.sql — profiles.role + first-Google-sign-in-is-admin
--
-- Bootstrap rule: the FIRST account that signs in with Google is promoted
-- to role 'admin' — exactly once. An advisory lock serialises concurrent
-- signups so only one account can ever claim the slot, and only a
-- google-provider signup is eligible (email/password accounts always
-- stay 'user'). Roles are written only by this security-definer trigger
-- or the engine's service role: the user-writable PostgREST policies
-- below refuse any row where role <> 'user', so nobody can self-promote.
--
-- The /admin panel (web/app/admin/AdminGate.tsx) reads role through the
-- user's own JWT under RLS; the engine's VANTIA_ADMIN_TOKEN stays the
-- second factor for engine-side writes.
--
-- Run order: psql "$DATABASE_URL" -f supabase/migrations/0007_admin_role.sql
-- ============================================================================

begin;

alter table profiles
    add column if not exists role text not null default 'user'
        check (role in ('user', 'admin'));

-- ── self-service policies: own row, never an admin role ─────────────────
drop policy if exists "profiles_insert_own" on profiles;
create policy "profiles_insert_own" on profiles
    for insert with check (
        (select auth.uid())::text = user_id and role = 'user');

drop policy if exists "profiles_update_own" on profiles;
create policy "profiles_update_own" on profiles
    for update using ((select auth.uid())::text = user_id)
    with check ((select auth.uid())::text = user_id and role = 'user');

-- ── bootstrap: first Google sign-in becomes the admin ───────────────────
create or replace function public.vantia_bootstrap_admin() returns trigger
language plpgsql security definer set search_path = public as $$
begin
    insert into public.profiles (user_id, email)
    values (new.id::text, coalesce(new.email, ''))
    on conflict (user_id) do nothing;

    -- exactly one first admin, even under concurrent signups; only a
    -- google-provider signup is ever eligible for the slot
    perform pg_advisory_xact_lock(hashtext('vantia_admin_bootstrap'));
    if new.raw_app_meta_data->'providers' ? 'google'
       and not exists (select 1 from public.profiles where role = 'admin') then
        update public.profiles set role = 'admin'
         where user_id = new.id::text;
    end if;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created_admin on auth.users;
create trigger on_auth_user_created_admin
    after insert on auth.users
    for each row execute function public.vantia_bootstrap_admin();

-- ── backfill: profiles for accounts created before this migration ───────
insert into public.profiles (user_id, email)
select id::text, coalesce(email, '') from auth.users
on conflict (user_id) do nothing;

-- An admin may already have signed in with Google before this migration
-- existed; promote the earliest google-provider account, once. If no
-- Google account exists yet, the slot stays open for the first login.
do $$
declare first_google uuid;
begin
    if exists (select 1 from public.profiles where role = 'admin') then
        return;
    end if;
    select id into first_google from auth.users
     where raw_app_meta_data->'providers' ? 'google'
     order by created_at asc
     limit 1;
    if first_google is not null then
        update public.profiles set role = 'admin'
         where user_id = first_google::text;
    end if;
end;
$$;

-- anon never touches profiles; authenticated keeps own-row access only
-- (RLS from 0005_rls.sql + the tightened policies above do the scoping)
revoke all on public.profiles from anon;
grant select, insert, update on public.profiles to authenticated;

commit;