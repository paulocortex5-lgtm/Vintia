"""Static /admin panel tests — present, hidden, and engine-wired.

The admin panel is reachable only by typing ``/admin`` directly:
noindex metadata, no links from any other page, absent from the
sitemap, disallowed in robots.txt — and the engine routes the React
console calls must actually exist. The `next build` gate compiles it.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
ADMIN_PAGE = WEB / "app" / "admin" / "page.tsx"
ADMIN_CONSOLE = WEB / "app" / "admin" / "AdminConsole.tsx"
ROBOTS = WEB / "app" / "robots.ts"
SITEMAP = (WEB / "app" / "sitemap.xml" / "route.ts").read_text("utf-8")


def test_admin_panel_files_exist():
    assert ADMIN_PAGE.exists(), "web/app/admin/page.tsx is missing"
    assert ADMIN_CONSOLE.exists(), "web/app/admin/AdminConsole.tsx is missing"
    assert ROBOTS.exists(), "web/app/robots.ts is missing"


def test_admin_page_is_noindex():
    text = ADMIN_PAGE.read_text("utf-8")
    assert "export const metadata" in text
    assert re.search(r"robots:\s*\{\s*index:\s*false", text), "/admin must opt out of indexing"


def test_admin_panel_is_absent_from_the_sitemap():
    assert "admin" not in SITEMAP, "/admin must stay out of the public sitemap"


def test_no_page_links_to_the_admin_panel():
    """The panel must not be visible on the user interface — no links."""
    offenders = []
    for source in sorted((WEB / "app").rglob("*.tsx")):
        if "app/admin" in source.as_posix():
            continue  # the panel itself links nowhere
        if 'href="/admin' in source.read_text("utf-8"):
            offenders.append(str(source.relative_to(ROOT)))
    assert offenders == [], f"pages linking to /admin (must stay hidden): {offenders}"


def test_robots_txt_disallows_admin():
    text = ROBOTS.read_text("utf-8")
    assert "robots" in text.lower()
    assert "/admin" in text
    assert "disallow" in text.lower()


def test_engine_ships_the_admin_routes_the_console_calls():
    api = (ROOT / "engine" / "api.py").read_text("utf-8")
    for route in (
        "/admin/overview",
        "/admin/tiers",
        "/admin/usage-tier",
        "/admin/credits",
        "/admin/credits/grant",
        "/admin/users/tier",
    ):
        assert route in api, route
    # fail-closed auth is module-level, not per-route
    admin_module = (ROOT / "engine" / "admin.py").read_text("utf-8")
    assert "admin_not_configured" in admin_module
    assert "VANTIA_ADMIN_TOKEN" in admin_module


def test_console_calls_admin_routes_with_bearer_auth():
    text = ADMIN_CONSOLE.read_text("utf-8")
    assert "Authorization" in text and "Bearer" in text
    # the admin key never enters the browser bundle (no NEXT_PUBLIC_ slot);
    # only its env-var *name* is shown as setup help — the value is typed in.
    assert "NEXT_PUBLIC_ADMIN_TOKEN" not in text
    assert "process.env" not in text
