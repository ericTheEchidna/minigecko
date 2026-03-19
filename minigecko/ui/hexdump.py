"""Hex dump formatting helpers for the file preview panel."""

from __future__ import annotations

from rich.text import Text

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


def _format_row(offset: int, chunk: bytes, width: int) -> Text:
    """Return a styled Rich Text object for one hex dump row."""
    t = Text(no_wrap=True)

    t.append(f"{offset:08x}", style="cyan")
    t.append("  ")

    for i, b in enumerate(chunk):
        if i > 0:
            t.append(" ")
        if b == 0x00:
            style = "bright_black"
        elif b == 0xFF:
            style = "yellow"
        else:
            style = ""
        t.append(f"{b:02x}", style=style)

    # Pad a short final row so the ASCII column stays aligned.
    if len(chunk) < width:
        t.append(" " * (3 * (width - len(chunk))))

    t.append("  ")
    t.append("|", style="bright_black")
    for b in chunk:
        if 0x20 <= b < 0x7F:
            t.append(chr(b), style="green")
        else:
            t.append(".", style="bright_black")
    t.append("|", style="bright_black")

    return t


def _iter_hexdump(data: bytes, width: int = _HEX_WIDTH):
    """Yield one Rich Text per data row (header/separator not included)."""
    for offset in range(0, len(data), width):
        yield _format_row(offset, data[offset:offset + width], width)
