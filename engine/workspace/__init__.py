"""User workspaces (tasks 8.2–8.4): rows, RLS-backed storage, isolation.

The SQL side (``supabase/migrations/0004_workspaces.sql`` +
``0005_rls.sql``) is the authority for tenancy: every row is owned by a
``user_id`` and row-level security scopes reads/writes to
``auth.uid()``. This package is the engine's *server-side* client:
it acts with the service role (the trusted backend), validates inputs,
and refuses loudly when Supabase is unconfigured — it never fakes a
successful write.
"""

from __future__ import annotations

from .service import WorkspaceService
from .storage import WorkspaceStorage

__all__ = ["WorkspaceService", "WorkspaceStorage"]
