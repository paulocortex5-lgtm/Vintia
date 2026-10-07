"""Verification & hardening layer (Phase 4).

Task 4.1 ships here: DNS/CNAME domain verification for launch domains.
"""

from __future__ import annotations

from .domain import PROVIDER_CNAME_TARGETS, DomainReport, verify_domain

__all__ = ["PROVIDER_CNAME_TARGETS", "DomainReport", "verify_domain"]
