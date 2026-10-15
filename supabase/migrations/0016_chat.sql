-- Migration 0016: platform chatbot tables + RLS (task 1.1 / Part 12.4).
-- Additive only: chat_conversations / chat_messages store the conversational
-- turns for ``POST /chat``.
--
-- RLS: a user's rows are visible/writable ONLY through `auth.uid()` — the
-- JWT `sub` claim Supabase Auth verifies server-side. The engine's service
-- role bypasses RLS natively as the trusted backend and mirrors through it
-- (best effort, never raises — STEP K).

begin;

create table if not exists public.chat_conversations (
    id            uuid primary key default gen_random_uuid(),
    user_id       text not null,
    title         text,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create table if not exists public.chat_messages (
    id               uuid primary key default gen_random_uuid(),
    conversation_id  uuid references public.chat_conversations(id) on delete cascade not null,
    user_id          text not null,
    role             text not null check (role in ('user', 'assistant')),
    content          text not null,
    created_at       timestamptz not null default now()
);

create index if not exists idx_chat_messages_conversation
    on public.chat_messages (conversation_id, created_at);
create index if not exists idx_chat_messages_user_created
    on public.chat_messages (user_id, created_at desc);

alter table public.chat_conversations enable row level security;
alter table public.chat_messages enable row level security;

-- ── conversations: own rows only ─────────────────────────────────────────
create policy "chat_conversations_select_own" on public.chat_conversations
    for select using ((select auth.uid())::text = user_id);
create policy "chat_conversations_insert_own" on public.chat_conversations
    for insert with check ((select auth.uid())::text = user_id);
create policy "chat_conversations_update_own" on public.chat_conversations
    for update using ((select auth.uid())::text = user_id)
    with check ((select auth.uid())::text = user_id);
create policy "chat_conversations_delete_own" on public.chat_conversations
    for delete using ((select auth.uid())::text = user_id);

-- ── messages: own rows only ──────────────────────────────────────────────
create policy "chat_messages_select_own" on public.chat_messages
    for select using ((select auth.uid())::text = user_id);
create policy "chat_messages_insert_own" on public.chat_messages
    for insert with check ((select auth.uid())::text = user_id);
create policy "chat_messages_update_own" on public.chat_messages
    for update using ((select auth.uid())::text = user_id)
    with check ((select auth.uid())::text = user_id);
create policy "chat_messages_delete_own" on public.chat_messages
    for delete using ((select auth.uid())::text = user_id);

grant select, insert, update on public.chat_conversations to authenticated;
grant select, insert, update on public.chat_messages to authenticated;

commit;
