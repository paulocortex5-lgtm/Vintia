"""Static deployment-config tests (tasks 6.1–6.7).

No Render/Vercel/Supabase credentials exist here, so these tests verify
what *can* be verified offline: configs parse, match each other, pin what
must be pinned, promise only what exists, and never embed secrets.
Deployments themselves are never claimed.
"""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

RENDER_YAML = (ROOT / "render.yaml").read_text("utf-8")
DOCKERFILE = (ROOT / "Dockerfile").read_text("utf-8")
VERCEL_JSON = json.loads((ROOT / "web" / "vercel.json").read_text("utf-8"))

#: Env vars that must never carry a literal value in git.
SECRET_KEYS = {
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWT_SECRET",
    "PADDLE_API_KEY",
    "PADDLE_WEBHOOK_SECRET",
    "PADDLE_PRICE_PACK_10K",
    "PADDLE_PRICE_PACK_50K",
    "PADDLE_PRICE_PACK_250K",
    "VANTIA_ALLOWED_ORIGINS",
}


# ── 6.4: render.yaml ───────────────────────────────────────────────────


def test_render_yaml_parses_with_one_web_service():
    blueprint = yaml.safe_load(RENDER_YAML)
    services = blueprint["services"]
    assert len(services) == 1
    service = services[0]
    assert service["type"] == "web"
    assert service["runtime"] == "docker"
    assert service["dockerfilePath"] == "./Dockerfile"
    assert (ROOT / "Dockerfile").exists()


def test_render_health_path_matches_the_engine():
    service = yaml.safe_load(RENDER_YAML)["services"][0]
    assert service["healthCheckPath"] == "/health"


def test_render_secrets_are_sync_false_never_literal():
    service = yaml.safe_load(RENDER_YAML)["services"][0]
    env = {e["key"]: e for e in service["envVars"]}
    for key in SECRET_KEYS:
        assert key in env, f"{key} missing from render.yaml"
        assert "value" not in env[key], f"{key} must not carry a literal value"
        assert env[key]["sync"] is False
    # nothing anywhere in the blueprint looks like a leaked credential
    assert "ghp_" not in RENDER_YAML
    assert "REPLACE_ME" not in RENDER_YAML


def test_render_deploys_are_deliberate():
    service = yaml.safe_load(RENDER_YAML)["services"][0]
    assert service["autoDeploy"] is False


# ── 6.3: Dockerfile reproducibility + hardening ────────────────────────


def test_base_image_is_pinned_to_an_immutable_digest():
    from_line = next(line for line in DOCKERFILE.splitlines() if line.startswith("FROM "))
    assert "@sha256:" in from_line, "base image must be digest-pinned (task 6.3)"
    digest = from_line.split("@sha256:")[1].strip()
    assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)


def test_pip_is_pinned_and_the_env_is_checked():
    assert "pip==25.2" in DOCKERFILE
    assert "pip check" in DOCKERFILE  # dependency coherence validated at build


def test_dockerfile_hygiene():
    assert "USER vantia" in DOCKERFILE  # non-root runtime
    assert "HEALTHCHECK" in DOCKERFILE and "/health" in DOCKERFILE
    # dependencies copied before code → layer caching
    assert DOCKERFILE.index("COPY requirements.txt") < DOCKERFILE.index("COPY engine")
    # no secrets or local state ever enter the image
    assert ".env" not in DOCKERFILE.replace(".env.example", "")
    assert ".vantia" not in DOCKERFILE


# ── 6.5: vercel.json ───────────────────────────────────────────────────


def test_vercel_config_is_nextjs_and_lockfile_reproducible():
    assert VERCEL_JSON["framework"] == "nextjs"
    assert VERCEL_JSON["installCommand"] == "npm ci"  # committed package-lock
    assert (ROOT / "web" / "package-lock.json").exists()
    assert VERCEL_JSON["buildCommand"] == "npm run build"


# ── 6.6: SUPABASE_SETUP.md ↔ migrations parity ────────────────────────


def test_supabase_runbook_lists_every_migration_in_order():
    setup = (ROOT / "docs" / "SUPABASE_SETUP.md").read_text("utf-8")
    actual = sorted(p.name for p in (ROOT / "supabase" / "migrations").glob("00*.sql"))
    assert actual, "no migrations found"
    for name in actual:
        assert name in setup, f"runbook never mentions {name}"
    # ordered rollout: the numbered list appears ascending
    positions = [setup.index(name) for name in sorted(actual)]
    assert positions == sorted(positions)


def test_supabase_runbook_is_honest_about_not_being_applied():
    setup = (ROOT / "docs" / "SUPABASE_SETUP.md").read_text("utf-8")
    assert "NOT APPLIED" in setup
    assert "relrowsecurity" in setup  # verification queries ship with it
    assert "vantia_jwt_hook" in setup  # dashboard step documented
    assert "user-workspaces" in setup  # storage bucket step documented


# ── 6.7: keep-alive documentation + workflow parity ───────────────────


def test_keep_alive_doc_documents_all_three_layers():
    doc = (ROOT / "docs" / "KEEP_ALIVE.md").read_text("utf-8")
    assert "keep-alive.yml" in doc
    assert "engine/keep_alive.py" in doc
    assert "every 14 min" in doc
    assert "VANTIA_SELF_PING" in doc


def test_keep_alive_workflow_has_the_documented_cron():
    workflow = (ROOT / ".github" / "workflows" / "keep-alive.yml").read_text("utf-8")
    assert "cron" in workflow and "*/14" in workflow


def test_promised_phase6_runbooks_all_exist():
    for name in ("RENDER_DEPLOY.md", "VERCEL_DEPLOY.md", "SUPABASE_SETUP.md", "KEEP_ALIVE.md"):
        assert (ROOT / "docs" / name).exists(), name
        text = (ROOT / "docs" / name).read_text("utf-8")
        assert "NOT DEPLOYED" in text or "NOT APPLIED" in text, f"{name} must state its status"
