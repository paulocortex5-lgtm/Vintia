"""Profile + workspace rows over Supabase (task 8.2, engine side).

The engine acts as the **trusted backend** (service role): it writes the
rows the RLS policies then scope per user. Every method refuses loudly
(``workspace_backend_unconfigured``) when Supabase is unconfigured —
silently returning empty lists here would read as "user has no data",
which is a lie, not a degradation.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..errors import WorkspaceError
from ..logging_config import utc_now
from .storage import _segment

__all__ = ["WorkspaceService"]


class WorkspaceService:
    """CRUD for profiles / workspaces / workspace_files via SupabaseClient."""

    def __init__(self, supabase_client: Any | None = None) -> None:
        from ..persistence import SupabaseClient

        self.client = supabase_client if supabase_client is not None else SupabaseClient()

    # ── Guards ──────────────────────────────────────────────────────
    def _require_backend(self) -> None:
        if not getattr(self.client, "configured", False):
            raise WorkspaceError(
                "Supabase is not configured; workspace rows cannot be read or written",
                code="workspace_backend_unconfigured",
            )

    # ── Profiles (8.2) ──────────────────────────────────────────────
    def ensure_profile(
        self, user_id: str, *, email: str = "", display_name: str = ""
    ) -> dict[str, Any]:
        """Idempotently create the user's profile row (tier defaults free)."""
        self._require_backend()
        _segment(user_id, "user_id")
        now = utc_now()
        row = {
            "user_id": user_id,
            "email": email,
            "display_name": display_name,
            "tier": "free",
            "created_at": now,
            "updated_at": now,
        }
        existing = self.client.query("profiles", {"user_id": f"eq.{user_id}"}, service=True)
        if existing:
            return dict(existing[0])
        self.client.upsert("profiles", [row], service=True)
        return row

    # ── Workspaces (8.2) ────────────────────────────────────────────
    def create_workspace(self, user_id: str, *, name: str = "default") -> dict[str, Any]:
        """Create one workspace owned by ``user_id``; returns the row."""
        self._require_backend()
        _segment(user_id, "user_id")
        workspace_id = uuid.uuid4().hex[:16]
        row = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "name": name,
            "created_at": utc_now(),
        }
        self.client.upsert("workspaces", [row], service=True)
        return row

    def list_workspaces(self, user_id: str) -> list[dict[str, Any]]:
        """Only ``user_id``'s workspaces — isolation at the query itself."""
        self._require_backend()
        return [
            dict(row)
            for row in self.client.query("workspaces", {"user_id": f"eq.{user_id}"}, service=True)
        ]

    def workspace_of(self, workspace_id: str) -> dict[str, Any] | None:
        """The owning row for ``workspace_id`` (``None`` when unknown)."""
        self._require_backend()
        rows = self.client.query("workspaces", {"workspace_id": f"eq.{workspace_id}"}, service=True)
        return dict(rows[0]) if rows else None

    def assert_owner(self, workspace_id: str, user_id: str) -> dict[str, Any]:
        """Raise ``workspace_forbidden`` unless ``user_id`` owns the workspace."""
        row = self.workspace_of(workspace_id)
        if row is None:
            raise WorkspaceError(
                f"workspace not found: {workspace_id}",
                code="workspace_not_found",
                workspace_id=workspace_id,
            )
        if row.get("user_id") != user_id:
            raise WorkspaceError(
                "workspace belongs to another user",
                code="workspace_forbidden",
                workspace_id=workspace_id,
            )
        return row

    # ── Files (8.2, mirrors 8.4 storage objects) ────────────────────
    def record_file(
        self,
        workspace_id: str,
        filename: str,
        *,
        size_bytes: int,
        content_type: str = "",
        storage_path: str = "",
    ) -> dict[str, Any]:
        """Upsert the metadata row for an uploaded file (idempotent per name)."""
        self._require_backend()
        row = {
            "file_id": f"{workspace_id}:{filename}",
            "workspace_id": workspace_id,
            "filename": filename,
            "size_bytes": int(size_bytes),
            "content_type": content_type,
            "storage_path": storage_path,
            "created_at": utc_now(),
        }
        self.client.upsert("workspace_files", [row], service=True)
        return row

    def list_files(self, workspace_id: str) -> list[dict[str, Any]]:
        self._require_backend()
        return [
            dict(row)
            for row in self.client.query(
                "workspace_files", {"workspace_id": f"eq.{workspace_id}"}, service=True
            )
        ]

    def delete_file(self, workspace_id: str, filename: str) -> None:
        """Remove the metadata row (the storage object is caller-side)."""
        self._require_backend()
        deleted = self.client.delete(
            "workspace_files", {"file_id": f"eq.{workspace_id}:{filename}"}, service=True
        )
        if not deleted:
            raise WorkspaceError(
                f"could not delete metadata row for {workspace_id}/{filename}",
                code="workspace_delete_failed",
            )
