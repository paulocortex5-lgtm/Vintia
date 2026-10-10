"""Workspace service tests (task 8.2, engine side) — owned rows, loud gaps."""

import pytest

from engine.errors import WorkspaceError
from engine.workspace import WorkspaceService


class FakeSupabase:
    """In-memory rows honoring the client's eq.-filter convention."""

    def __init__(self, configured: bool = True) -> None:
        self.configured = configured
        self.rows: dict[str, list[dict]] = {}

    def query(self, table, filters, select="*", *, service=False):
        column, raw_filter = next(iter(filters.items()))
        raw = raw_filter.partition("eq.")[2]
        return [r for r in self.rows.get(table, []) if str(r.get(column)) == raw]

    def upsert(self, table, rows, *, service=False):
        keyed = self.rows.setdefault(table, [])
        for row in rows:
            key = row.get("file_id") or row.get("workspace_id") or row.get("user_id")
            keyed = [r for r in keyed if key not in r.values()]
            keyed.append(row)
        self.rows[table] = keyed
        return True

    def delete(self, table, filters, *, service=False):
        column, raw_filter = next(iter(filters.items()))
        raw = raw_filter.partition("eq.")[2]
        before = len(self.rows.get(table, []))
        self.rows[table] = [r for r in self.rows.get(table, []) if str(r.get(column)) != raw]
        return len(self.rows[table]) < before


def test_unconfigured_backend_refuses_loudly():
    service = WorkspaceService(FakeSupabase(configured=False))
    for call in (
        lambda: service.ensure_profile("u1"),
        lambda: service.create_workspace("u1"),
        lambda: service.list_workspaces("u1"),
        lambda: service.record_file("ws", "cv.md", size_bytes=1),
    ):
        with pytest.raises(WorkspaceError) as excinfo:
            call()
        assert excinfo.value.code == "workspace_backend_unconfigured"


def test_profile_is_created_once_and_defaults_to_free():
    fake = FakeSupabase()
    service = WorkspaceService(fake)
    first = service.ensure_profile("u1", email="a@example.com", display_name="Ada")
    assert first["tier"] == "free"
    second = service.ensure_profile("u1")  # idempotent — keeps the first row
    assert second["email"] == "a@example.com"
    assert len(fake.rows["profiles"]) == 1


def test_profile_rejects_a_path_traversing_user_id():
    service = WorkspaceService(FakeSupabase())
    with pytest.raises(WorkspaceError) as excinfo:
        service.ensure_profile("../admin")
    assert excinfo.value.code == "workspace_path_invalid"


def test_workspaces_and_files_flow():
    fake = FakeSupabase()
    service = WorkspaceService(fake)
    service.ensure_profile("u1")
    workspace = service.create_workspace("u1", name="job-hunt")
    assert workspace["user_id"] == "u1"
    assert service.list_workspaces("u1") == [workspace]
    assert service.list_workspaces("u2") == []  # isolation at the query itself

    service.record_file(
        workspace["workspace_id"], "cv.md", size_bytes=5, storage_path="u1/ws/cv.md"
    )
    files = service.list_files(workspace["workspace_id"])
    assert files[0]["filename"] == "cv.md"
    service.delete_file(workspace["workspace_id"], "cv.md")
    assert service.list_files(workspace["workspace_id"]) == []


def test_assert_owner_forbids_a_foreign_user():
    fake = FakeSupabase()
    service = WorkspaceService(fake)
    service.ensure_profile("u1")
    workspace = service.create_workspace("u1")
    assert service.assert_owner(workspace["workspace_id"], "u1")["user_id"] == "u1"

    with pytest.raises(WorkspaceError) as excinfo:
        service.assert_owner(workspace["workspace_id"], "u2")
    assert excinfo.value.code == "workspace_forbidden"

    with pytest.raises(WorkspaceError) as excinfo2:
        service.assert_owner("does-not-exist", "u1")
    assert excinfo2.value.code == "workspace_not_found"


def test_delete_failure_is_reported_not_swallowed():
    class NoDelete(FakeSupabase):
        def delete(self, table, filters, *, service=False):
            return False

    service = WorkspaceService(NoDelete())
    with pytest.raises(WorkspaceError) as excinfo:
        service.delete_file("ws", "cv.md")
    assert excinfo.value.code == "workspace_delete_failed"
