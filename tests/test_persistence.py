"""Persistence tests: Supabase degrades gracefully + git fallback mirrors.

The non-network tests cover the critical guarantee — an unconfigured or
unreachable Supabase must never raise: Git stays authoritative (§0.7).
"""

from pathlib import Path

from engine.json_utils import load_json
from engine.persistence import SupabaseClient
from engine.persistence.fallback import GitFallback


def test_supabase_client_unconfigured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    client = SupabaseClient()
    assert client.configured is False
    assert client.reachable() is False
    assert client.upsert("vantia_state", [{"body": "{}"}]) is False
    assert client.sync_state({"run_count": 1}) is False
    assert client.log_cost({"usd": 0.0}) is False
    assert client.log_llm_usage({"provider": "groq"}) is False
    assert client.log_artifact({"id": "x"}) is False


def test_supabase_client_rejects_placeholder_keys(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "REPLACE_ME")
    assert SupabaseClient().configured is False


def test_supabase_client_network_failures_do_not_raise(monkeypatch):
    # Point at an unreachable URL with a short timeout. Network failures must
    # never raise: git stays authoritative.
    monkeypatch.setenv("SUPABASE_URL", "https://127.0.0.1:59999")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "a-real-looking-key")
    client = SupabaseClient(timeout=0.2)
    assert client.configured is True
    assert client.reachable() is False
    assert client.upsert("vantia_state", [{"body": "{}"}]) is False
    assert client.log_cost({"usd": 0.0}) is False
    assert client.log_llm_usage({"provider": "groq"}) is False
    assert client.log_artifact({"id": "x"}) is False


def test_git_fallback_mirrors_state_and_artifacts(tmp_path):
    fallback = GitFallback(repo_dir=str(tmp_path))
    state = {"run_count": 1, "last_completed_task": "0.1", "in_progress_task": None}
    mirror = fallback.mirror_state(state)
    body = load_json(mirror)
    assert body["run_count"] == 1
    assert body["last_completed_task"] == "0.1"
    assert body["state_file"] == ".vantia/state/state.json"
    assert (tmp_path / ".vantia" / "mirror.json").exists()

    source = tmp_path / "resume.json"
    source.write_text("{}", encoding="utf-8")
    copied = fallback.copy_artifact(str(source))
    assert Path(copied) != source
    assert Path(copied).exists()
    assert Path(copied).read_text(encoding="utf-8") == "{}"
    # Idempotent: a second copy lands at the same target.
    assert fallback.copy_artifact(str(source)) == copied


def test_git_fallback_copies_unknown_extensions_to_artifacts(tmp_path):
    fallback = GitFallback(repo_dir=str(tmp_path))
    source = tmp_path / "notes.txt"
    source.write_text("hello", encoding="utf-8")
    target = fallback.copy_artifact(str(source))
    assert Path(target).name == "notes.txt"
    assert Path(target).parent == (tmp_path / ".vantia" / "artifacts")


def test_missing_artifact_is_a_file_error(tmp_path):
    """A missing source must fail loudly; execute_step validates artifacts first."""
    fallback = GitFallback(repo_dir=str(tmp_path))
    try:
        fallback.copy_artifact(str(tmp_path / "nope.json"))
        assert False, "expected FileNotFoundError for a missing source"
    except FileNotFoundError:
        pass
    # makedirs runs before the copy, so an empty artifacts dir is expected.
    assert list((tmp_path / ".vantia" / "artifacts").glob("*")) == []
