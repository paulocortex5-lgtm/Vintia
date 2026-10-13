"""Static SEO / web-surface tests (tasks 5.4 / 5.5).

The engine can't render pages, so these verify what text files can prove:
real metadata replaces the create-next-app stock, schema.org JSON-LD ships
on the layout and every landing page, the sitemap lists exactly the public
surface (no dead links), and each promised page exists with a unique
title. The `next build` gate compiles everything.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

#: The six SEO landing pages (task 5.5), sitemap parity enforced below.
LANDING_PAGES = ("ats", "improve", "cover-letter", "scholarships", "jobs", "credits")

LAYOUT = (WEB / "app" / "layout.tsx").read_text("utf-8")
SITEMAP = (WEB / "app" / "sitemap.xml" / "route.ts").read_text("utf-8")


# ── 5.4: layout metadata + JSON-LD + honest sitemap ────────────────────


def test_layout_has_real_metadata_not_the_create_next_app_stock():
    assert "Create Next App" not in LAYOUT
    assert "metadataBase" in LAYOUT
    assert '"%s | Vantia"' in LAYOUT  # title template
    assert "openGraph" in LAYOUT
    assert "twitter" in LAYOUT
    assert 'type: "website"' in LAYOUT


def test_layout_ships_schema_org_website_json_ld():
    assert 'type="application/ld+json"' in LAYOUT
    assert '"@type": "WebSite"' in LAYOUT
    assert '"@type": "Organization"' in LAYOUT
    assert "schema.org" in LAYOUT


def test_sitemap_lists_exactly_the_public_surface():
    locs = re.findall(r"<loc>\$\{baseUrl\}(/[^<]*)?</loc>", SITEMAP)
    paths = sorted(p.lstrip("/") for p in locs)  # root captures "" after lstrip
    assert paths == sorted([""] + list(LANDING_PAGES)), paths
    # app/utility routes never masquerade as SEO pages
    for hidden in ("dashboard", "workspace", "status", "waitlist", "credits/purchase"):
        assert hidden not in paths


def test_every_sitemap_entry_is_a_real_page():
    for slug in LANDING_PAGES:
        page = WEB / "app" / slug / "page.tsx"
        assert page.exists(), f"sitemap promises /{slug} but {page} is missing"


# ── 5.5: the six landing pages ─────────────────────────────────────────


def test_each_landing_page_has_metadata_json_ld_and_real_content():
    titles = []
    for slug in LANDING_PAGES:
        text = (WEB / "app" / slug / "page.tsx").read_text("utf-8")
        assert "export const metadata" in text, slug
        assert "description:" in text, slug
        assert 'type="application/ld+json"' in text, slug
        assert "@type" in text, slug  # schema.org block exists
        # real content + the sign-in CTA that retired the waitlist button
        assert "<h1" in text and 'href="/dashboard"' in text, slug
        title = re.search(r'title: "([^"]+)"', text)
        assert title, slug
        titles.append(title.group(1))
    assert len(set(titles)) == 6, "landing page titles must be unique for SEO"


def test_marketing_pages_retired_the_waitlist_cta():
    """With accounts live, no marketing page may push the waitlist anymore.

    The /waitlist route itself stays functional (double opt-in, old
    links) — it is simply no longer linked from anywhere public.
    """
    offenders = []
    for source in sorted((WEB / "app").rglob("*.tsx")):
        if "app/waitlist" in source.as_posix():
            continue  # the waitlist pages themselves
        if 'href="/waitlist"' in source.read_text("utf-8"):
            offenders.append(str(source.relative_to(ROOT)))
    assert offenders == [], f"pages still linking /waitlist (retired CTA): {offenders}"


def test_waitlist_pages_exist_for_the_opt_in_flow():
    assert (WEB / "app" / "waitlist" / "page.tsx").exists()
    confirm = WEB / "app" / "waitlist" / "confirm" / "page.tsx"
    assert confirm.exists()
    text = confirm.read_text("utf-8")
    assert "waitlist/confirm" in text and "token" in text


def test_engine_ships_the_waitlist_routes_the_pages_call():
    api = (ROOT / "engine" / "api.py").read_text("utf-8")
    for route in ("/waitlist/subscribe", "/waitlist/confirm", "/waitlist/stats"):
        assert route in api, route
    migrations = sorted(p.name for p in (ROOT / "supabase" / "migrations").glob("000*.sql"))
    assert "0006_waitlist.sql" in migrations  # the table exists in the rollout
