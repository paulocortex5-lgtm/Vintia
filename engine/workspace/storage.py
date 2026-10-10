"""Private file storage on Supabase Storage (task 8.4).

One bucket (``workspaces.storage_bucket`` from state, default
``user-workspaces``), object paths ``<user_id>/<workspace_id>/<filename>``
so the bucket's storage policies can mirror the same ownership predicate
the RLS policies use (first path segment = ``auth.uid()``).

Rules (carried from the local pipeline layer):

* **Validate before the network** — size cap
  (``workspaces.max_file_size_mb``) and extension allow-list
  (``workspaces.allowed_file_types``) come from state; a violation raises
  before any HTTP call.
* **Traversal-proof** — every path segment is checked; ``..``, ``/``,
  empty names and absolute paths are refused (``workspace_path_invalid``).
* **Honest degradation** — unconfigured Supabase raises
  ``storage_unconfigured``; unreachable or 4xx/5xx responses raise with
  the status attached. A download of a missing file is
  ``workspace_file_missing`` — never empty bytes.
"""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

from ..errors import WorkspaceError
from ..json_utils import load_json
from ..state_manager import DEFAULT_STATE_DIR, VantiaState, seed_path

__all__ = ["WorkspaceStorage"]

_PLACEHOLDER = "REPLACE_ME"
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_DEFAULT_MAX_MB = 10
_DEFAULT_TYPES = ("pdf", "docx", "doc", "txt", "md")


def workspace_config(state_dir: str | None = None) -> dict[str, Any]:
    """The state ``workspaces`` block (seed fallback, like credits config)."""
    try:
        data = VantiaState(state_dir or DEFAULT_STATE_DIR).load()
    except Exception:  # noqa: BLE001 — missing/corrupt state falls back to the seed
        data = load_json(seed_path())
    if not isinstance(data, dict):
        return {}
    block = data.get("workspaces")
    return dict(block) if isinstance(block, dict) else {}


def _segment(value: str, label: str) -> str:
    """Validate one path segment; refuse traversal and separators."""
    if not value or value in (".", "..") or "/" in value or "\\" in value:
        raise WorkspaceError(
            f"invalid {label}: {value!r}", code="workspace_path_invalid", segment=value
        )
    if not _SEGMENT_RE.match(value):
        raise WorkspaceError(
            f"invalid {label}: {value!r}", code="workspace_path_invalid", segment=value
        )
    return value


class WorkspaceStorage:
    """Supabase Storage client for one bucket (task 8.4)."""

    def __init__(
        self,
        *,
        bucket: str | None = None,
        url: str | None = None,
        service_key: str | None = None,
        http_client: httpx.Client | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        cfg = config if config is not None else workspace_config()
        self.bucket = bucket or str(cfg.get("storage_bucket") or "user-workspaces")
        self.max_bytes = int(cfg.get("max_file_size_mb") or _DEFAULT_MAX_MB) * 1024 * 1024
        allowed = cfg.get("allowed_file_types")
        self.allowed_types = tuple(str(t).lower() for t in allowed) if allowed else _DEFAULT_TYPES
        self.url = (url if url is not None else os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.service_key = (
            service_key
            if service_key is not None
            else os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        )
        self._client = http_client

    # ── Configuration guards ────────────────────────────────────────
    @property
    def configured(self) -> bool:
        return bool(
            self.url.startswith("http")
            and self.service_key
            and _PLACEHOLDER not in self.service_key
        )

    def _require_configured(self) -> None:
        if not self.configured:
            raise WorkspaceError(
                "Supabase Storage is not configured (SUPABASE_URL / service role key)",
                code="storage_unconfigured",
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
            "Content-Type": "application/octet-stream",
        }

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    # ── Validation (before any network) ─────────────────────────────
    def validate(self, filename: str, content: bytes) -> str:
        """Extension + size check; returns the validated (bare) filename."""
        name = _segment(filename, "filename")
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if extension not in self.allowed_types:
            raise WorkspaceError(
                f"file type {extension or '(none)'!r} not allowed; "
                f"allowed: {', '.join(self.allowed_types)}",
                code="file_type_not_allowed",
                filename=name,
            )
        if len(content) > self.max_bytes:
            raise WorkspaceError(
                f"file is {len(content)} bytes; limit is {self.max_bytes}",
                code="file_too_large",
                size=len(content),
                limit=self.max_bytes,
            )
        return name

    def object_path(self, user_id: str, workspace_id: str, filename: str) -> str:
        """``<user>/<workspace>/<file>`` with every segment validated."""
        return "/".join(
            (
                _segment(user_id, "user_id"),
                _segment(workspace_id, "workspace_id"),
                _segment(filename, "filename"),
            )
        )

    # ── CRUD ────────────────────────────────────────────────────────
    def upload(
        self, user_id: str, workspace_id: str, filename: str, content: bytes
    ) -> dict[str, Any]:
        """PUT one object; returns path + size metadata."""
        self._require_configured()
        name = self.validate(filename, content)
        path = self.object_path(user_id, workspace_id, name)
        response = self._http().put(
            f"{self.url}/storage/v1/object/{self.bucket}/{path}",
            content=content,
            headers=self._headers(),
        )
        if response.status_code >= 400:
            raise WorkspaceError(
                f"storage upload failed (HTTP {response.status_code})",
                code="storage_upload_failed",
                status=response.status_code,
            )
        return {"path": path, "filename": name, "size_bytes": len(content), "bucket": self.bucket}

    def download(self, user_id: str, workspace_id: str, filename: str) -> bytes:
        """GET one object; missing files raise, never return empty bytes."""
        self._require_configured()
        path = self.object_path(user_id, workspace_id, filename)
        response = self._http().get(
            f"{self.url}/storage/v1/object/{self.bucket}/{path}",
            headers=self._headers(),
        )
        if response.status_code == 404:
            raise WorkspaceError(
                f"workspace file not found: {path}", code="workspace_file_missing", path=path
            )
        if response.status_code == 403:
            raise WorkspaceError(
                f"storage access denied: {path}", code="workspace_forbidden", path=path
            )
        if response.status_code >= 400:
            raise WorkspaceError(
                f"storage download failed (HTTP {response.status_code})",
                code="storage_download_failed",
                status=response.status_code,
            )
        return response.content

    def delete(self, user_id: str, workspace_id: str, filename: str) -> None:
        """DELETE one object; 404 is an honest ``workspace_file_missing``."""
        self._require_configured()
        path = self.object_path(user_id, workspace_id, filename)
        response = self._http().request(
            "DELETE",
            f"{self.url}/storage/v1/object/{self.bucket}/{path}",
            headers=self._headers(),
        )
        if response.status_code == 404:
            raise WorkspaceError(
                f"workspace file not found: {path}", code="workspace_file_missing", path=path
            )
        if response.status_code >= 400:
            raise WorkspaceError(
                f"storage delete failed (HTTP {response.status_code})",
                code="storage_delete_failed",
                status=response.status_code,
            )
