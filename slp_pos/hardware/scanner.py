"""USB barcode scanner support (SRS FR-3.1, FR-3.2).

A keyboard-emulation ("wedge") scanner needs no driver and no code to read it:
it types the barcode characters and sends Enter, exactly as if a very fast
typist used the keyboard. The checkout screen keeps its search box focused, and
on Enter it looks the text up as a barcode before falling back to a name search.

This module holds only small pure helpers for cleaning and recognising scanned
input, so they can be unit-tested without any hardware.
"""

from __future__ import annotations

import re

# CR, LF, Tab and other control characters a scanner may add as a prefix/suffix.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# Common retail barcodes: UPC-E (6), UPC-A (12), EAN-8 (8), EAN-13 (13). Allow a
# little slack for store-assigned codes.
_MIN_BARCODE_LEN = 6
_MAX_BARCODE_LEN = 14


def normalize_scan(raw: str) -> str:
    """Remove stray control characters and trim surrounding whitespace.

    Inner spaces are kept, so a deliberate multi-word product search
    ("fresh milk") is left untouched.
    """
    if not raw:
        return ""
    return _CONTROL_CHARS.sub("", raw).strip()


def looks_like_barcode(text: str) -> bool:
    """True if ``text`` is all digits and a plausible barcode length."""
    text = text.strip()
    return text.isdigit() and _MIN_BARCODE_LEN <= len(text) <= _MAX_BARCODE_LEN
