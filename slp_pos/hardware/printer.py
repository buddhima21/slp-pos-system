"""Send a plain-text receipt to the printer (SRS FR-5.1, 6.1).

v1.0 prints plain text through the default Windows printer: the receipt file is
handed to the OS "print" verb, which routes it via whatever driver the thermal
or standard printer uses. ESC/POS formatting is a later upgrade (SRS 6.1).

Every function here is best-effort. If the printer is off, unplugged, or out of
paper the call raises :class:`PrinterError`; the checkout flow catches it, warns
the cashier, and still completes the sale (SRS 9.1).
"""

from __future__ import annotations

import os
from pathlib import Path


class PrinterError(Exception):
    """The receipt could not be sent to the printer."""


def print_text_file(path: str | Path) -> None:
    """Send an existing text file to the default printer.

    Uses ``os.startfile(path, "print")`` on Windows, which is asynchronous - it
    queues the job and returns. The file must stay on disk until the spooler has
    read it, so callers print the saved receipt file rather than a temp copy.
    """
    path = Path(path)
    if not path.exists():
        raise PrinterError(f"Receipt file not found: {path}")

    if os.name != "nt" or not hasattr(os, "startfile"):
        raise PrinterError(
            "Automatic printing is only supported on Windows in v1.0. "
            f"The receipt was saved to {path}."
        )

    try:
        os.startfile(str(path), "print")  # type: ignore[attr-defined]
    except OSError as exc:
        raise PrinterError(
            f"Could not send the receipt to the printer ({exc}). "
            f"It was saved to {path}."
        ) from exc
