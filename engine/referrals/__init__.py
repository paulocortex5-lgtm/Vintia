"""Referral program package (task 15.11)."""

from .manager import (
    REFERRAL_BONUS,
    code_for,
    generate_code,
    history_for,
    record_signup,
    referrer_for_code,
)

__all__ = [
    "REFERRAL_BONUS",
    "code_for",
    "generate_code",
    "history_for",
    "record_signup",
    "referrer_for_code",
]
