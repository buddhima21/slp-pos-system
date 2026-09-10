"""Small helpers to turn user-entered text into numbers.

Raise ``ValueError`` with a friendly, field-labelled message. Each service
catches these and re-raises them as its own error type so the UI can show the
message directly.
"""

from __future__ import annotations


def parse_money(value: object, label: str) -> float:
    try:
        number = round(float(str(value).strip()), 2)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number.")
    if number < 0:
        raise ValueError(f"{label} cannot be negative.")
    return number


def parse_count(value: object, label: str) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")
    if number < 0:
        raise ValueError(f"{label} cannot be negative.")
    return number
