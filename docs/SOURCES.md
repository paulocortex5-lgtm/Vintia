# Vantia — Job & Data Sources

**Session 7 product direction (authoritative):**

1. **Everything fetchable is fetched.** Jobs listed directly on
   government websites/portals are first-class sources alongside the
   commercial portals.
2. **Active only.** Listings whose closing date has passed are dropped
   from searches (`filter_active`) and refused by `load()`
   (`code="listing_inactive"`).
3. **Sponsorship is a tag, never a filter.** We do **not** limit the
   platform to visa-sponsored jobs — that would hide opportunities.
   All jobs from all sources are kept; listings that *do* offer
   sponsorship are tagged `visa_sponsorship=True` so users can filter
   *towards* them. Nothing is ever filtered *for lacking* sponsorship.
4. **All European countries** are in the search database
   (`engine/sources/countries.py`, 50 entries) with targeting so
   searches can pinpoint countries with opportunity + less competition.

## What task "2.3 — Visa register fetchers (UK/DE/AU)" means

Registers are **government lists of employers licensed to sponsor work
visas** — employer names, not job ads. They badge employers on our
listings. Implementation: `engine/sources/registers.py`.

| Country | Register | Status |
|---|---|---|
| 🇬🇧 UK | GOV.UK *Register of licensed sponsors: workers* — CSV attachment, updated almost daily | **Live** — `fetch_uk_register()` downloads page → CSV → normalised names |
| 🇦🇺 AU | Public register of approved sponsors (Migration Amendment (Combatting Migrant Exploitation) Act 2026, s.140GD) | **Mandated, not yet published** (deadline 2026-10-08) — `fetch_au_register()` raises `RegisterPending`; activates when Home Affairs ships it |
| 🇩🇪 DE | *None exists* — Germany's *Vorabzustimmung* is granted per employer+employee and is not a public list | Documented via `GERMANY_PUBLISHES_REGISTER = False`; German sponsorship is judged per posting from the listing text |

## Register coverage: every country of interest (50 + AU)

Only three countries have *verified register facts* (UK published, AU
pending, DE none) — that's why the task was labelled UK/DE/AU: those
were the founding markets when task 2.3 was planned. **Coverage itself
is not limited to them.** `engine/sources/registers.py` resolves
*every* country in the 50-country database plus AU:

* `register_spec(iso2)` — explicit registry (`_REGISTER_SPECS`) for the
  three verified facts; every other country of interest resolves
  through the country database's `sponsor_register` status (currently
  `none` = *no known public register*). Unknown ISO codes raise
  `FetchError(code="register_country_unknown")` rather than being
  silently assumed register-free.
* `fetch_register(iso2, fetcher)` — dispatches on the status:
  `published` runs the generic page→CSV pipeline (the UK
  implementation already takes the publication URL as a parameter, so
  any future published register plugs in as **one data row**, no code
  change); `pending` raises `RegisterPending`; `none` returns an empty
  `SponsorRegister`.
* `fetch_registers(codes, fetcher)` — bulk fetch that skips pending
  countries (non-fatal: badges simply stay untagged until the
  register publishes).

The policy is unchanged: registers **tag**, they never drop jobs, and
no country is excluded from the platform for lacking a register.

## Source inventory

| Kind | Sources | Module |
|---|---|---|
| Commercial portals | Greenhouse, Lever, Workday (W/G/L) | `engine/sources/portals/` |
| Government job APIs | 🇩🇪 Federal Employment Agency (`rest.arbeitsagentur.de`, public `X-API-Key`) | `engine/sources/government.py` |
| Government portals (human) | Catalogued per country: `pes_url` in the countries DB (Find-a-job UK, France Travail, NAV, SEPE, …) | `engine/sources/countries.py` |
| Sponsor registers | All 50 European countries + AU resolve via `register_spec()` / `fetch_register()`; UK CSV live, AU pending (2026-10-08), DE none, others = no known public register (empty badge set) | `engine/sources/registers.py` |

Every network call goes through `Fetcher` (robots gate → per-domain rate
limit → retry/backoff → size cap), so new sources inherit the politeness
policy automatically.

## Targeting: opportunity + less competition

`search_targets()` ranks countries by `CountryTarget.score()`:

* +3 machine-fetchable government jobs API (we can actually harvest it)
* +1 official public employment portal catalogued
* +2 employer sponsor register published (+0.5 pending)
* +1 EU/EEA (free movement for our users)
* −unemployment/10 once a verified Eurostat rate is populated
  (`unemployment_rate` field exists; left `None` until a citable
  snapshot is embedded — no invented statistics)

Pinpointing: `search_targets(iso2_filter={"PT", "ES"})` for explicit
country picks; `eu_eea_only=True` / `with_api_only=True` for structural
pre-filters. **No country is ever excluded for lacking a register.**

## Adding a country source (checklist)

1. Verify the endpoint (fetch the official docs/example — no guessed URLs).
2. Add/extend an adapter in `government.py` routed through `Fetcher`.
3. Update the country row in `countries.py` (`gov_jobs_api`/`pes_url`).
4. Fixture-based tests (MockTransport — no network, ever).
5. Never gate on sponsorship; always drop closed listings.
