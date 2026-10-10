"""End-to-end workspace isolation test (task 8.5).

Two users, one bucket, zero network: identity comes only from a verified
JWT (`require_user`), rows are scoped per user at the query itself, the
ownership guard refuses cross-user access *before* any storage call, and
traversal/expired-token paths leave the storage untouched. Storage HTTP
is served by MockTransport; the touched-host assertion pins the footprint.
"""

import time

import httpx
import jwt as pyjwt
import pytest

from engine.auth import require_user
from engine.errors import AuthError, WorkspaceError
from engine.workspace import WorkspaceService, WorkspaceStorage

SECRET = "e2e-workspace-jwt-secret"
BUCKET = "user-workspaces"
SB_HOST = "supabase.test"

CONFIG = {
    "storage_bucket": BUCKET,
    "max_file_size_mb": 1,
    "allowed_file_types": ["pdf", "docx", "doc", "txt", "md"],
}


def make_token(sub: str, *, exp_offset: int = 3600) -> str:
    payload = {
        "sub": sub,
        "role": "authenticated",
        "aud": "authenticated",
        "exp": int(time.time()) + exp_offset,
    }
    return pyjwt.encode(payload, SECRET, algorithm="HS256")


class FakeSupabase:
    """In-memory rows honoring the eq.-filter convention (service role)."""

    configured = True

    def __init__(self) -> None:
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


def make_bucket_handler(store: dict[str, bytes], seen: list[str]):
    """Mock Supabase Storage; every touch is recorded for the host pin."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        prefix = f"/storage/v1/object/{BUCKET}/"
        assert request.url.path.startswith(prefix)
        path = request.url.path[len(prefix) :]
        if request.method == "PUT":
            store[path] = request.content
            return httpx.Response(200, json={"Key": path})
        if request.method == "GET":
            if path not in store:
                return httpx.Response(404, text="not found")
            return httpx.Response(200, content=store[path])
        if request.method == "DELETE":
            store.pop(path, None)
            return httpx.Response(204)
        return httpx.Response(405)

    return handler


@pytest.fixture()
def journey():
    store: dict[str, bytes] = {}
    seen: list[str] = []
    storage = WorkspaceStorage(
        url=f"https://{SB_HOST}",
        service_key="service-key-e2e",
        http_client=httpx.Client(transport=httpx.MockTransport(make_bucket_handler(store, seen))),
        config=CONFIG,
    )
    service = WorkspaceService(FakeSupabase())
    return store, seen, storage, service


def test_two_users_are_fully_isolated(journey):
    _store, seen, storage, service = journey

    # — user A: sign in, set up, upload —
    ctx_a = require_user(f"Bearer {make_token('user-a')}", secret=SECRET)
    service.ensure_profile(ctx_a.user_id, email="a@example.com", display_name="Ada")
    workspace_a = service.create_workspace(ctx_a.user_id, name="job-hunt")
    meta = storage.upload(ctx_a.user_id, workspace_a["workspace_id"], "cv.md", b"# Ada's CV")
    service.record_file(
        workspace_a["workspace_id"],
        meta["filename"],
        size_bytes=meta["size_bytes"],
        storage_path=meta["path"],
    )
    assert storage.download(ctx_a.user_id, workspace_a["workspace_id"], "cv.md") == b"# Ada's CV"
    assert service.list_workspaces(ctx_a.user_id) == [workspace_a]

    # — user B: verified, but sees none of A's world —
    ctx_b = require_user(f"Bearer {make_token('user-b')}", secret=SECRET)
    service.ensure_profile(ctx_b.user_id)
    assert service.list_workspaces(ctx_b.user_id) == []  # isolation at the query

    # the ownership guard refuses before any storage traffic
    with pytest.raises(WorkspaceError) as excinfo:
        service.assert_owner(workspace_a["workspace_id"], ctx_b.user_id)
    assert excinfo.value.code == "workspace_forbidden"

    seen_before = len(seen)
    with pytest.raises(WorkspaceError):
        # the supported call sequence always guards first
        service.assert_owner(workspace_a["workspace_id"], ctx_b.user_id)
        storage.download(ctx_b.user_id, workspace_a["workspace_id"], "cv.md")
    assert len(seen) == seen_before  # zero storage calls happened for B

    # every storage path stays user-scoped (bucket policies can mirror it)
    assert all(
        url.startswith(f"https://{SB_HOST}/storage/v1/object/{BUCKET}/user-a/") for url in seen
    )

    # touched-host pin
    hosts = {httpx.URL(u).host for u in seen}
    assert hosts <= {SB_HOST}, hosts


def test_expired_token_stops_before_any_work(journey):
    _store, seen, _storage, _service = journey
    with pytest.raises(AuthError) as excinfo:
        require_user(f"Bearer {make_token('user-a', exp_offset=-10)}", secret=SECRET)
    assert excinfo.value.code == "token_expired"
    assert seen == []  # identity failed → nothing else ran


def test_traversal_upload_never_reaches_storage(journey):
    store, seen, storage, _service = journey
    with pytest.raises(WorkspaceError) as excinfo:
        storage.upload("user-a", "ws1", "../../etc/passwd.md", b"x")
    assert excinfo.value.code == "workspace_path_invalid"
    assert seen == []
    assert store == {}


def test_full_delete_round_trip_is_isolated(journey):
    store, _seen, storage, service = journey
    ctx_a = require_user(f"Bearer {make_token('user-a')}", secret=SECRET)
    ws = service.create_workspace(ctx_a.user_id)
    storage.upload(ctx_a.user_id, ws["workspace_id"], "cv.md", b"data")
    service.record_file(ws["workspace_id"], "cv.md", size_bytes=4)
    path = f"user-a/{ws['workspace_id']}/cv.md"
    assert path in store

    storage.delete(ctx_a.user_id, ws["workspace_id"], "cv.md")
    service.delete_file(ws["workspace_id"], "cv.md")
    assert path not in store
    assert service.list_files(ws["workspace_id"]) == []
    with pytest.raises(WorkspaceError) as excinfo:
        storage.download(ctx_a.user_id, ws["workspace_id"], "cv.md")
    assert excinfo.value.code == "workspace_file_missing"
