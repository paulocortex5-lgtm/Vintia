# Tech Context

## Backend
Python 3.12 (local venv is 3.14.4 at /tmp/vantia-venv), FastAPI,
Uvicorn, supabase-py, Pydantic v2, jsonschema, httpx, Click, structlog,
tenacity, pytest, pytest-cov, ruff, mypy, pdfplumber, python-docx,
pycountry, dnspython, filelock, tiktoken, rapidfuzz, paddle-python-sdk.

## Frontend
Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, @supabase/supabase-js,
SWR, Inter + JetBrains Mono fonts, dark mode default.

## Database
Supabase Postgres with RLS on all tenant tables. Storage bucket
"user-workspaces". Auth via email + OAuth + magic link.
Credentials are PLACEHOLDERS (REPLACE_ME) at this stage, so all
network-success paths are untested until real keys arrive.

## LLM Providers (free tier)
NVIDIA NIM, Groq, Cerebras, SambaNova, Google Gemini, OpenRouter,
Mistral, Cloudflare Workers AI, GitHub Models, Together AI, HuggingFace,
Cohere.

## LLM Providers (paid, opt-in)
OpenAI, Anthropic, Google Vertex, DeepSeek, xAI, Mistral Paid, Cohere
Paid, Together Paid, Fireworks, Perplexity.

## Deployment
Render free tier (backend Docker container), Vercel Hobby (frontend),
Supabase free tier (database), GitHub Actions (keep-alive + build),
Paddle Billing (payments, sandbox until launch).

## Local Dev Notes (established Session 1)
- Package is installed editable (`pip install -e .`), so the `vantia`
  console script works. venv lives at `/tmp/vantia-venv`.
- Test suite: `python -m pytest --cov=engine -q` → 165 tests, 91%
  line coverage of engine/ (18 test files).
- Payments: Paddle Billing only (Merchant of Record) via
  `paddle-python-sdk`; Stripe is absent from the repo by design
  (task 0.0, R56–R60). Webhook signature checks use stdlib
  `hmac`/`hashlib` — no extra dependency.
- `engine/api.py` uses the deprecated `@app.on_event("startup")`; a
  later task should migrate to the FastAPI lifespan context manager.
- GitHub push uses an inline `oauth2:<token>@github.com/...` URL so the
  credential is never persisted to `.git/config` or any committed file.