"""Stub-elimination + country-tab tests (tasks 15.15 / 15.16 §19.4, §20.3).

Scans the web source for the banned stub phrases and asserts the pipeline
page renders both pipelines with live/tier-gated steps (never a stub).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

BANNED = ("launching soon", "coming soon", "not implemented")


def _web_sources() -> list[Path]:
    files = []
    for base in ("app", "components", "lib"):
        d = WEB / base
        if not d.exists():
            continue
        for path in d.rglob("*"):
            if path.suffix in (".tsx", ".ts") and "node_modules" not in path.parts:
                files.append(path)
    return files


def test_no_banned_stub_phrases_in_web():
    hits = []
    for path in _web_sources():
        text = path.read_text(encoding="utf-8").casefold()
        for phrase in BANNED:
            if phrase in text:
                hits.append(f"{path.relative_to(ROOT)}: {phrase}")
    assert not hits, f"stub phrases remain: {hits}"


def test_pipeline_page_renders_both_pipelines():
    text = (WEB / "app" / "pipeline" / "page.tsx").read_text(encoding="utf-8")
    assert "Jobs Pipeline" in text
    assert "Scholarships Pipeline" in text
    # 10 job steps + 7 scholarship steps are declared.
    assert text.count("status: \"live\"") + text.count('status: "locked"') >= 17


def test_pipeline_country_tabs_include_ca_au_nz():
    text = (WEB / "app" / "pipeline" / "page.tsx").read_text(encoding="utf-8")
    for code in ("CA", "AU", "NZ"):
        assert f'"{code}"' in text


def test_new_frontend_routes_exist():
    for route in ("applications", "alerts", "referrals"):
        assert (WEB / "app" / route / "page.tsx").exists(), f"/{route} page missing"
