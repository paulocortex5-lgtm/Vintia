"""Workspace storage tests (task 8.4) — validate first, honest failures."""

import httpx
import pytest

from engine.errors import WorkspaceError
from engine.workspace.storage import WorkspaceStorage, workspace_config

URL = "https://sb.test"
KEY = "service-role-key"

CONFIG = {
    "storage_bucket": "user-workspaces",
    "max_file_size_mb": 1,  # 1 MiB for fast tests
    "allowed_file_types": ["pdf", "docx", "doc", "txt", "md"],
}


def make_storage(handler, **overrides):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return WorkspaceStorage(
        url=URL, service_key=KEY, http_client=client, config=CONFIG, **overrides
    ), client


# ── Configuration ──────────────────────────────────────────────────────


def test_config_falls_back_to_the_packaged_seed():
    cfg = workspace_config(state_dir="/nonexistent/state")
    assert cfg["storage_bucket"] == "user-workspaces"
    assert cfg["max_file_size_mb"] == 10
    assert "pdf" in cfg["allowed_file_types"]


def test_unconfigured_refuses_every_operation(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    storage = WorkspaceStorage(config=CONFIG)
    assert storage.configured is False
    for call in (
        lambda: storage.upload("u", "ws", "cv.md", b"x"),
        lambda: storage.download("u", "ws", "cv.md"),
        lambda: storage.delete("u", "ws", "cv.md"),
    ):
        with pytest.raises(WorkspaceError) as excinfo:
            call()
        assert excinfo.value.code == "storage_unconfigured"

    placeholder = WorkspaceStorage(url="REPLACE_ME", service_key=KEY, config=CONFIG)
    assert placeholder.configured is False


# ── Validation before any network ──────────────────────────────────────


def test_upload_validates_before_any_http():
    seen: list[str] = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200)

    storage, _ = make_storage(handler)
    with pytest.raises(WorkspaceError) as e1:
        storage.upload("u1", "ws1", "malware.exe", b"x")
    assert e1.value.code == "file_type_not_allowed"
    with pytest.raises(WorkspaceError) as e2:
        storage.upload("u1", "ws1", "cv.md", b"x" * (2 * 1024 * 1024))
    assert e2.value.code == "file_too_large"
    assert e2.value.context["limit"] == 1024 * 1024
    assert seen == []  # nothing left the process


def test_traversal_is_refused_in_every_segment():
    storage, _ = make_storage(lambda request: httpx.Response(200))
    bad = [
        ("u1", "ws1", "../cv.md"),
        ("u1", "ws1", ".."),
        ("u1", "ws1", "a/b.md"),
        ("u1", "ws1", ""),
        ("../root", "ws1", "cv.md"),
        ("u1", "..", "cv.md"),
        ("u1", "ws1", "cv\\md.md"),
    ]
    for user_id, workspace_id, filename in bad:
        with pytest.raises(WorkspaceError) as excinfo:
            storage.object_path(user_id, workspace_id, filename)
        assert excinfo.value.code == "workspace_path_invalid", (user_id, workspace_id, filename)


# ── CRUD over MockTransport ────────────────────────────────────────────


def test_upload_puts_the_user_scoped_object():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = request.content
        return httpx.Response(200)

    storage, _ = make_storage(handler)
    meta = storage.upload("user-a", "ws42", "cv.md", b"# Ada")
    assert captured["url"] == f"{URL}/storage/v1/object/user-workspaces/user-a/ws42/cv.md"
    assert captured["auth"] == f"Bearer {KEY}"
    assert captured["body"] == b"# Ada"
    assert meta == {
        "path": "user-a/ws42/cv.md",
        "filename": "cv.md",
        "size_bytes": 5,
        "bucket": "user-workspaces",
    }


def test_download_missing_file_raises_instead_of_empty_bytes():
    storage, _ = make_storage(lambda request: httpx.Response(404, text="not found"))
    with pytest.raises(WorkspaceError) as excinfo:
        storage.download("user-a", "ws42", "cv.md")
    assert excinfo.value.code == "workspace_file_missing"


def test_download_forbidden_and_server_errors_are_loud():
    storage, _ = make_storage(lambda request: httpx.Response(403))
    with pytest.raises(WorkspaceError) as excinfo:
        storage.download("user-a", "ws42", "cv.md")
    assert excinfo.value.code == "workspace_forbidden"

    storage500, _ = make_storage(lambda request: httpx.Response(500))
    with pytest.raises(WorkspaceError) as excinfo2:
        storage500.download("user-a", "ws42", "cv.md")
    assert excinfo2.value.code == "storage_download_failed"
    assert excinfo2.value.context["status"] == 500


def test_upload_and_delete_failures_carry_the_status():
    storage403, _ = make_storage(lambda request: httpx.Response(403))
    with pytest.raises(WorkspaceError) as excinfo:
        storage403.upload("user-a", "ws42", "cv.md", b"x")
    assert excinfo.value.code == "storage_upload_failed"

    storage404, _ = make_storage(lambda request: httpx.Response(404))
    with pytest.raises(WorkspaceError) as excinfo2:
        storage404.delete("user-a", "ws42", "cv.md")
    assert excinfo2.value.code == "workspace_file_missing"

    seen: list[str] = []

    def ok(request):
        seen.append(request.method)
        return httpx.Response(204)

    storage_ok, _ = make_storage(ok)
    storage_ok.delete("user-a", "ws42", "cv.md")
    assert seen == ["DELETE"]
