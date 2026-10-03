"""Git fallback persistence (task 0.7).

When Supabase is down, the mirror stays local and is committed to the
``vantia-state`` branch — git is the authoritative store (§2).
"""

from __future__ import annotations

import logging
import os
import shutil

from ..json_utils import atomic_write_json
from ..logging_config import utc_now

LOGGER = logging.getLogger("vantia.persistence.fallback")


class GitFallback:
    """Keep a git-committable copy of state and artifacts."""

    def __init__(self, repo_dir: str = ".") -> None:
        self.repo_dir = repo_dir
        self.mirror_path = os.path.join(repo_dir, ".vantia", "mirror.json")
        self.artifact_dir = os.path.join(repo_dir, ".vantia", "artifacts")

    def mirror_state(self, state: dict) -> str:
        """Write ``.vantia/mirror.json`` describing the authoritative state."""
        body = {
            "mirrored_at": utc_now(),
            "state_file": ".vantia/state/state.json",
            "run_count": state.get("run_count"),
            "last_completed_task": state.get("last_completed_task"),
            "in_progress_task": state.get("in_progress_task"),
        }
        atomic_write_json(self.mirror_path, body)
        return self.mirror_path

    def copy_artifact(self, src: str, relative: str | None = None) -> str:
        """Copy an artifact into ``.vantia/artifacts/`` for committing."""
        target_name = relative or os.path.basename(src)
        os.makedirs(self.artifact_dir, exist_ok=True)
        target = os.path.join(self.artifact_dir, target_name)
        if os.path.abspath(src) != os.path.abspath(target):
            shutil.copy2(src, target)
        return target
