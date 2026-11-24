"""Hex dump formatting helpers for the file preview panel."""

from __future__ import annotations

_HEX_WIDTH = 16  # bytes per row
_MAX_BYTES = 10 * 2**20  # cap display at 10 MB


def _col_header_markup(width: int = _HEX_WIDTH) -> str:
    """Column-number labels as Rich markup (no OFFSET prefix)."""
    cols = " ".join(f"{i:02x}" for i in range(width))
    ascii_cols = "0123456789abcdef"[:width]
    return f"[bold]{cols}[/]  [bright_black]|[/][bold]{ascii_cols}[/][bright_black]|[/]"


def _separator_markup(width: int = _HEX_WIDTH) -> str:
    """Separator rule as Rich markup."""
    sep_len = 8 + 2 + width * 3 - 1 + 2 + 1 + width + 1
    return f"[bright_black]{'─' * sep_len}[/]"
