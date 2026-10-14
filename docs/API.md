# Vantia Public API

Programmatic access for universities, career services and research teams.
All endpoints are served from the same engine that powers the Vantia web
app; scoring is the deterministic 12-point ATS rubric (task 9.4) and
equivalence lookups read the embedded credential registry.

**Base URL:** `https://vantia-engine.onrender.com`

## Authentication

Send your key in the `Authorization` header as a Bearer token:

```
Authorization: Bearer vantia_sk_xxxxxxxxxxxxxxxxxxxx
```

Keys are created by an administrator (`POST /api-keys`) and shown **once**
at creation — only a SHA-256 hash is stored, so a lost key cannot be
recovered. An unknown or malformed key returns **401**.

## Rate limiting

Per-key sliding window (60s). `free` keys: **10 requests/min**;
`business` keys: **100 requests/min**. Every response carries:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
```

When the window is exhausted the API returns **429** with a `Retry-After`
header (seconds until the oldest hit leaves the window).

---

## `POST /v1/ats/score`

Score a CV against a job description with the 12-point rubric.

**Request**

```json
{
  "cv": "Jane Doe\nSenior Backend Engineer\nSkills: Python, Django, ...",
  "job_title": "Senior Backend Engineer",
  "job_description": "5+ years Python, Django, PostgreSQL. Bachelor required."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `cv` | string | yes | Raw CV/resume text (plain or markdown) |
| `job_description` | string | no | Target posting text |
| `job_title` | string | no | Target role title |

**Response `200`**

```json
{
  "overall_score": 78.5,
  "report": {
    "overall_score": 78.5,
    "categories": { "keyword_match": 82.0, "...": 0.0 },
    "matched_keywords": ["python", "django"],
    "missing_keywords": ["kubernetes"],
    "suggestions": [ { "category": "location_match", "hint": "..." } ]
  }
}
```

**Errors:** `401` invalid key · `422` missing `cv` · `429` rate limited.

**Example (curl)**

```bash
curl -X POST https://vantia-engine.onrender.com/v1/ats/score \
  -H "Authorization: Bearer vantia_sk_..." \
  -H "Content-Type: application/json" \
  -d '{"cv":"...","job_description":"..."}'
```

---

## `GET /v1/equivalence/{country}/{credential}`

Look up a credential's equivalence for a target country. Reads the
embedded registry (Anabin / ENIC / WES / VETASSESS / NZQA crosswalks);
the `advice` field states provenance or the honest instruction to seek
ENIC-NARIC recognition.

**Example**

```
GET /v1/equivalence/GB/bachelor%20of%20engineering
```

**Response `200`**

```json
{
  "country": "GB",
  "credential": "bachelor of engineering",
  "match": { "title": "BEng (Hons)", "eqf_level": 6, "basis": "ENIC-UK" },
  "target_title": "Bachelor with Honours",
  "advice": "equivalence derived from: ENIC-UK"
}
```

`match` is `null` when nothing is in the registry — never a fabricated
equivalence. **Errors:** `401` invalid key · `429` rate limited.

---

## Admin key management

These endpoints are gated by the platform admin token
(`Authorization: Bearer <VANTIA_ADMIN_TOKEN>`), not by an API key.

### `POST /api-keys`

```json
{ "owner_email": "registry@university.edu", "name": "Careers service", "tier": "business" }
```

Returns `{ "key": "vantia_sk_...", "record": { "id": "...", "tier": "business", "rate_limit_per_min": 100 } }`.
**Save the `key` now — it is never shown again.**

### `GET /api-keys`

List keys (hashes redacted): `{ "keys": [...], "total": 2 }`.

### `DELETE /api-keys/{id}`

Revoke a key by its `id`: `{ "deleted": true, "id": "..." }`.
