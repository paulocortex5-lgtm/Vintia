# syntax=docker/dockerfile:1
# Reproducibility (task 6.3): the base image is pinned to an immutable
# digest (python:3.12-slim, resolved via the Docker Hub tags API on
# 2026-10-10) and pip is pinned to a known release, so a rebuild can
# never silently drift. Refresh both pins deliberately, never by luck.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first: layer caching means code edits never re-resolve deps.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir pip==25.2 \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check

COPY engine ./engine
COPY pyproject.toml README.md ./
RUN pip install -e .

# Non-root runtime user (6.3 hardening): the engine never needs root.
RUN useradd --create-home --shell /usr/sbin/nologin vantia
USER vantia

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "engine.api:app", "--host", "0.0.0.0", "--port", "8000"]
