"""Domain verification tests (task 4.1) — fake resolvers, zero DNS traffic."""

from engine.verification import PROVIDER_CNAME_TARGETS, verify_domain


def make_resolver(table: dict[tuple[str, str], list[str]]):
    def resolve(name: str, rtype: str) -> list[str]:
        return list(table.get((name.lower(), rtype), []))

    return resolve


def test_render_cname_matches_the_expected_provider():
    resolver = make_resolver(
        {
            ("vantia.onrender.com", "A"): ["203.0.113.10"],
            ("app.vantia.ai", "CNAME"): ["vantia.onrender.com"],
        }
    )
    report = verify_domain("app.vantia.ai", expect="render", resolver=resolver)
    assert report.status == "ok" and report.ok
    assert report.matched is True
    assert report.cnames == ("vantia.onrender.com",)
    assert report.addresses == ("203.0.113.10",)
    assert "render" in report.note


def test_vercel_cname_against_render_expectation_fails_loudly():
    resolver = make_resolver({("www.vantia.ai", "CNAME"): ["cname.vercel-dns.com"]})
    report = verify_domain("www.vantia.ai", expect="render", resolver=resolver)
    assert report.status == "cname_mismatch" and not report.ok
    assert report.matched is False
    assert "does not match" in report.note


def test_nxdomain_when_dns_answers_nothing():
    report = verify_domain("nope.vantia.ai", expect="vercel", resolver=make_resolver({}))
    assert report.status == "nxdomain" and not report.ok
    assert report.cnames == () and report.addresses == ()
    assert "no CNAME or A records" in report.note


def test_without_expectation_the_report_only_observes():
    resolver = make_resolver({("vantia.ai", "A"): ["198.51.100.7"]})
    report = verify_domain("vantia.ai", resolver=resolver)
    assert report.status == "ok"
    assert report.matched is None  # an observation, not a pass/fail claim
    assert "observations only" in report.note


def test_explicit_suffix_expectation_matches_any_depth():
    resolver = make_resolver(
        {
            ("alias.vantia.ai", "CNAME"): ["d123.cloudfront.net"],
            ("d123.cloudfront.net", "A"): ["1.2.3.4"],
        }
    )
    report = verify_domain("alias.vantia.ai", expect="cloudfront.net", resolver=resolver)
    assert report.matched is True and report.status == "ok"


def test_cname_chain_is_followed_to_the_leaf():
    resolver = make_resolver(
        {
            ("a.example", "CNAME"): ["b.example"],
            ("b.example", "CNAME"): ["c.example.prod.onrender.com"],
            ("c.example.prod.onrender.com", "A"): ["9.9.9.9"],
        }
    )
    report = verify_domain("a.example", expect="render", resolver=resolver)
    assert report.cnames == ("b.example", "c.example.prod.onrender.com")
    assert report.addresses == ("9.9.9.9",)
    assert report.status == "ok"


def test_cname_loops_are_broken():
    resolver = make_resolver(
        {("x.example", "CNAME"): ["y.example"], ("y.example", "CNAME"): ["x.example"]}
    )
    report = verify_domain("x.example", resolver=resolver)
    assert report.status == "ok"
    assert len(report.cnames) <= 2  # loop guard stops the walk


def test_report_serialises_for_the_status_page():
    resolver = make_resolver({("app.vantia.ai", "CNAME"): ["app.onrender.com"]})
    payload = verify_domain("app.vantia.ai", expect="render", resolver=resolver).to_dict()
    assert payload["domain"] == "app.vantia.ai"
    assert payload["ok"] is True
    assert payload["checked_at"].endswith("Z")
    assert payload["expectation"] == "render"
    assert set(PROVIDER_CNAME_TARGETS) == {"render", "vercel"}
