"""Phase 5 checks: barcode scanner input helpers (SRS FR-3.1, FR-3.2)."""

from __future__ import annotations

import pytest

from slp_pos.hardware.scanner import looks_like_barcode, normalize_scan


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("4001234567890\n", "4001234567890"),   # trailing newline suffix
        ("4001234567890\r\n", "4001234567890"),  # CR+LF
        ("\t4001234567890", "4001234567890"),    # leading tab prefix
        ("  4001234567890  ", "4001234567890"),  # surrounding spaces
        ("fresh milk", "fresh milk"),            # inner space kept for name search
        ("", ""),
    ],
)
def test_normalize_scan(raw, expected):
    assert normalize_scan(raw) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("4001234567890", True),   # EAN-13
        ("036000291452", True),    # UPC-A
        ("12345678", True),        # EAN-8
        ("12345", False),          # too short
        ("123456789012345", False),  # too long
        ("ABC123", False),         # not all digits
        ("fresh milk", False),
        ("", False),
    ],
)
def test_looks_like_barcode(text, expected):
    assert looks_like_barcode(text) is expected
