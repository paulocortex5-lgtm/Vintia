"""Incident reporting (task 4.4) — blocked tasks become GitHub issues.

``open_issue`` tries the ``gh`` CLI first; when the CLI is absent or the
push/issue credential is refused (the environment's known HTTP 403), it
**never loses the incident**: the report is written as a Markdown draft
under ``issues_dir`` and indexed in ``index.json``. Either way the
caller gets a dict saying exactly what happened.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable

from .json_utils import atomic_write_json, load_json
from .logging_config import utc_now

__all__ = ["ISSUES_DIR", "open_issue", "slugify"]

ISSUES_DIR = ".vantia/issues"

#: (returncode, output) — injected in tests, subprocess in production
RunnerFn = Callable[[list[str]], tuple[int, str]]


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
    return slug[:80] or "incident"


def _gh_runner(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
        return 127, str(exc)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _index(issues_dir: str, row: dict) -> None:
    path = os.path.join(issues_dir, "index.json")
    data = load_json(path, default=[])
    rows = data if isinstance(data, list) else []
    rows.append(row)
    atomic_write_json(path, rows)


def open_issue(
    title: str,
    body: str,
    *,
    repo: str | None = None,
    labels: tuple[str, ...] = ("vantia", "blocked-task"),
    runner: RunnerFn | None = None,
    issues_dir: str = ISSUES_DIR,
) -> dict[str, object]:
    """Open a GitHub issue for ``title``/``body``; draft on any failure.

    Returns ``{"method": "gh", "url"/"detail": ...}`` when the CLI
    succeeded, else ``{"method": "draft", "path": ...}``.
    """
    run = runner if runner is not None else (_gh_runner if shutil.which("gh") else None)
    if run is not None:
        cmd = ["gh", "issue", "create"]
        if repo:
            cmd += ["-R", repo]
        cmd += ["-t", title, "-b", body]
        for label in labels:
            cmd += ["-l", label]
        try:
            code, output = run(cmd)
        except Exception as exc:  # noqa: BLE001 — a broken runner still gets a draft
            code, output = 1, f"incident runner failed: {exc}"
        if code == 0:
            row = {"title": title, "method": "gh", "detail": output, "at": utc_now()}
            _index(issues_dir, row)
            return {"method": "gh", "title": title, "detail": output}

    path = _write_draft(title, body, issues_dir)
    _index(
        issues_dir,
        {"title": title, "method": "draft", "path": path, "at": utc_now()},
    )
    return {"method": "draft", "title": title, "path": path}


def _write_draft(title: str, body: str, issues_dir: str) -> str:
    os.makedirs(issues_dir, exist_ok=True)
    path = os.path.join(issues_dir, f"{slugify(title)}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            f"# {title}\n\n{body}\n\n---\n_created by vantia incident reporter ({utc_now()})_\n"
        )
    return path
