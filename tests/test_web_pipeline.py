"""Static tool-gate + application-pipeline tests.

The four product tools (ATS scanner, CV improver, cover letter, credits
dashboard + packs) must render only behind a Supabase session, and the
two-track pipeline page (jobs / scholarships) must actually link every
step it promises, ship in the sitemap, and be reachable from the
dashboard. The session check itself is client-side by design (the session
lives in localStorage), so these verify the wiring; the `next build` gate
compiles it.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
APP = WEB / "app"

GATE = WEB / "components" / "RequireSession.tsx"
PIPELINE = APP / "pipeline" / "page.tsx"
SITEMAP = (APP / "sitemap.xml" / "route.ts").read_text("utf-8")


# ── the session gate ───────────────────────────────────────────────────


def test_require_session_gate_ships_and_is_client_side():
    assert GATE.exists(), "web/components/RequireSession.tsx is missing"
    text = GATE.read_text("utf-8")
    assert '"use client"' in text
    assert "loadSession" in text  # the real session, never faked
    # both honest sign-in paths are offered
    assert "signInWithGoogle" in text and 'href="/dashboard"' in text
    assert "process.env" not in text  # gates carry no env access


TOOL_WRAPPERS = {
    APP / "ats" / "page.tsx": (APP / "ats" / "AtsTool.tsx", "AtsScanner"),
    APP / "improve" / "page.tsx": (APP / "improve" / "ImproveTool.tsx", "CvImprover"),
    APP / "cover-letter" / "page.tsx": (
        APP / "cover-letter" / "CoverLetterTool.tsx",
        "CoverLetterGenerator",
    ),
}


def test_each_tool_page_renders_through_the_session_gate():
    for page, (wrapper, component) in TOOL_WRAPPERS.items():
        assert wrapper.exists(), wrapper
        page_text = page.read_text("utf-8")
        assert wrapper.stem in page_text, f"{page} no longer renders {wrapper.stem}"
        # the raw tool component is no longer imported by the public page
        assert f'from "./{component}"' not in page_text, page
        text = wrapper.read_text("utf-8")
        assert '"use client"' in text, wrapper
        assert "RequireSession" in text, wrapper
        # the tool loads client-only: signed-out visitors never receive it
        assert "ssr: false" in text, wrapper
        assert f'import("./{component}")' in text, wrapper


def test_credits_dashboard_and_packs_are_gated():
    dashboard = (APP / "credits" / "dashboard" / "page.tsx").read_text("utf-8")
    assert "RequireSession" in dashboard
    assert "CreditsDashboardInner" in dashboard  # content mounts only behind the gate
    purchase = (APP / "credits" / "purchase" / "page.tsx").read_text("utf-8")
    assert "RequireSession" in purchase
    # packs are bought against the verified session, never a typed placeholder
    assert "vantia_user_id" not in purchase
    assert "loadSession" in purchase


# ── the two-track pipeline ─────────────────────────────────────────────


def test_pipeline_page_ships_with_both_tracks_and_metadata():
    assert PIPELINE.exists(), "web/app/pipeline/page.tsx is missing"
    text = PIPELINE.read_text("utf-8")
    assert "export const metadata" in text
    assert 'type="application/ld+json"' in text
    assert 'href="/dashboard"' in text  # step one is always the account
    assert 'id="jobs"' in text
    assert 'id="scholarships"' in text


def test_pipeline_links_every_step_it_promises():
    text = PIPELINE.read_text("utf-8")
    # the Track renderer links `step.href`, so the paths appear as data
    # literals (plus /dashboard as the CTA link)
    assert 'href={step.href}' in text
    for href in (
        "/dashboard",
        "/ats",
        "/improve",
        "/cover-letter",
        "/jobs",
        "/scholarships",
        "/credits/dashboard",
    ):
        assert f'"{href}"' in text, f"pipeline never links {href}"
    # every step is now live or tier-gated — nothing ships as a stub. (This
    # assertion was flipped from `in` to `not in` under RULE 0.3: the prior
    # contract required a "launching soon" placeholder, which R29 / Part 19
    # explicitly forbids. See tests/test_stub_elimination.py for the guard.)
    assert "launching soon" not in text


def test_pipeline_is_listed_in_the_sitemap():
    assert "${baseUrl}/pipeline" in SITEMAP


def test_dashboard_offers_both_pipeline_tracks():
    dashboard = (APP / "dashboard" / "Dashboard.tsx").read_text("utf-8")
    assert 'href="/pipeline#jobs"' in dashboard
    assert 'href="/pipeline#scholarships"' in dashboard


def test_marketing_pages_point_at_the_pipeline():
    home = (APP / "page.tsx").read_text("utf-8")
    assert 'href="/pipeline"' in home
    assert 'href="/pipeline#jobs"' in (APP / "jobs" / "page.tsx").read_text("utf-8")
    assert 'href="/pipeline#scholarships"' in (APP / "scholarships" / "page.tsx").read_text(
        "utf-8"
    )
