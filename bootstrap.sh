#!/usr/bin/env bash
# Vantia bootstrap — materialises the repository structure (§3).
# Idempotent: safe to run repeatedly. Exits 0 on success.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

DIRS=(
  ".github/workflows"
  ".vantia/state"
  ".vantia/artifacts/ats"
  ".vantia/artifacts/sop"
  ".vantia/artifacts/proposals"
  ".vantia/artifacts/cover_letters"
  ".vantia/artifacts/cv_improvements"
  ".vantia/cache/llm"
  ".vantia/cache/dns"
  ".vantia/cache/fetches"
  ".vantia/quarantine/fees"
  ".vantia/quarantine/injection"
  ".vantia/quarantine/domain"
  "engine/persistence"
  "engine/auth"
  "engine/workspace"
  "engine/ats"
  "engine/improve"
  "engine/credits"
  "engine/llm"
  "engine/prompts"
  "engine/schemas"
  "engine/sources"
  "engine/verify"
  "engine/generators"
  "web/app/dashboard"
  "web/app/workspace/files"
  "web/app/workspace/scans"
  "web/app/ats/[id]"
  "web/app/improve"
  "web/app/cover-letter"
  "web/app/credits/purchase"
  "web/lib"
  "tests/e2e"
  "docs"
)

for d in "${DIRS[@]}"; do
  mkdir -p "$d"
done

# Ensure Python packages are importable.
for pkg in engine engine/persistence engine/auth engine/workspace engine/ats \
           engine/improve engine/credits engine/llm; do
  [ -f "$pkg/__init__.py" ] || : > "$pkg/__init__.py"
done

echo "bootstrap: ok ($ROOT)"
exit 0
