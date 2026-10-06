"""Scholarship engine (Phase 3).

Tasks 3.1 (database), 3.4 (credential mapper) and 3.5 (window
tracker) ship here; generators (3.2/3.3) and the pipeline (3.6) layer
on top in the next run. Deterministic and offline: the database is
static, sourced data — no network is required to match, map or check
a window.
"""

from __future__ import annotations

from .database import (
    EUROPEAN_PROGRAMME_COUNTRIES,
    SCHOLARSHIPS,
    Scholarship,
    get_scholarship,
    search_scholarships,
)
from .mapper import map_credential
from .windows import open_windows, window_status, windows

__all__ = [
    "EUROPEAN_PROGRAMME_COUNTRIES",
    "SCHOLARSHIPS",
    "Scholarship",
    "get_scholarship",
    "map_credential",
    "open_windows",
    "search_scholarships",
    "window_status",
    "windows",
]
