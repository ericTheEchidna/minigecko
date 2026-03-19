"""Interactive hex dump widget with hover cross-highlighting.

Row layout (bytes_per_row = 16):
  00000000  xx xx xx xx xx xx xx xx xx xx xx xx xx xx xx xx  |................|
  ^col 0    ^col 10                                          ^col 59^col 60   ^col 76

Geometry constants:
  HEX_START   = 10          hex byte i at cols  10+i*3, 10+i*3+1
  ASCII_START = 60          ascii byte i at col  60+i
  ASCII_END   = 75          (inclusive, 0-based)
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text
from textual.geometry import Region, Size
from textual.scroll_view import ScrollView
from textual.strip import Strip

_BYTES_PER_ROW = 16
_HEX_START = 10
_ASCII_START = 60
_ASCII_END = 75        # inclusive

_CONSOLE = Console(highlight=False)


def _row_to_strip(offset: int, chunk: bytes, hovered_col: int | None, total_width: int) -> Strip:
    """Render one hex-dump row as a Textual Strip."""
    n = _BYTES_PER_ROW
    t = Text(no_wrap=True)

    t.append(f"{offset:08x}", style="cyan")
    t.append("  ")

    for i, b in enumerate(chunk):
        if i > 0:
            t.append(" ")
        hover = hovered_col == i
        if b == 0x00:
            base = "bright_black"
        elif b == 0xFF:
            base = "yellow"
        else:
            base = ""
        style = ("reverse " + base).strip() if hover else base
        t.append(f"{b:02x}", style=style)

    if len(chunk) < n:
        t.append("   " * (n - len(chunk)))

    t.append("  ")
    t.append("|", style="bright_black")

    for i, b in enumerate(chunk):
        hover = hovered_col == i
        if 0x20 <= b < 0x7F:
            t.append(chr(b), style="reverse green" if hover else "green")
        else:
            t.append(".", style="reverse bright_black" if hover else "bright_black")

    t.append("|", style="bright_black")

    segments = list(t.render(_CONSOLE))
    return Strip(segments).adjust_cell_length(total_width)


class HexDumpView(ScrollView):
    """Virtual-rendering hex dump panel with hover cross-highlighting."""

    DEFAULT_CSS = """
    HexDumpView {
        height: 1fr;
        scrollbar-gutter: stable;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._data: bytes = b""
        self._hovered_byte: int | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, data: bytes) -> None:
        """Display *data* in the hex dump."""
        self._data = data
        self._hovered_byte = None
        row_count = max(1, (len(data) + _BYTES_PER_ROW - 1) // _BYTES_PER_ROW)
        self.virtual_size = Size(self.size.width or 78, row_count)
        self.scroll_home(animate=False)
        self.refresh()

    def clear(self) -> None:
        self._data = b""
        self._hovered_byte = None
        self.virtual_size = Size(0, 0)
        self.refresh()

    def jump_to_offset(self, byte_offset: int) -> None:
        row = byte_offset // _BYTES_PER_ROW
        self.scroll_to(x=0, y=row, animate=False)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_line(self, y: int) -> Strip:
        row = y + self.scroll_offset.y
        offset = row * _BYTES_PER_ROW

        if not self._data or offset >= len(self._data):
            return Strip.blank(self.size.width)

        chunk = self._data[offset : offset + _BYTES_PER_ROW]

        hovered_col: int | None = None
        if self._hovered_byte is not None:
            hovered_row, col = divmod(self._hovered_byte, _BYTES_PER_ROW)
            if hovered_row == row:
                hovered_col = col

        return _row_to_strip(offset, chunk, hovered_col, self.size.width)

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def on_mouse_move(self, event) -> None:
        x = event.offset.x
        y = event.offset.y
        content_row = y + self.scroll_offset.y

        col: int | None = None
        if _HEX_START <= x <= _ASCII_START - 4:  # hex region
            rel = x - _HEX_START
            if rel % 3 != 2:
                candidate = rel // 3
                if candidate < _BYTES_PER_ROW:
                    col = candidate
        elif _ASCII_START <= x <= _ASCII_END:     # ASCII region
            col = x - _ASCII_START

        new_hover: int | None = None
        if col is not None:
            idx = content_row * _BYTES_PER_ROW + col
            if idx < len(self._data):
                new_hover = idx

        if new_hover != self._hovered_byte:
            self._refresh_byte_row(self._hovered_byte)
            self._hovered_byte = new_hover
            self._refresh_byte_row(self._hovered_byte)

    def on_leave(self) -> None:
        if self._hovered_byte is not None:
            self._refresh_byte_row(self._hovered_byte)
            self._hovered_byte = None

    def _refresh_byte_row(self, byte_idx: int | None) -> None:
        if byte_idx is None:
            return
        row = byte_idx // _BYTES_PER_ROW
        viewport_y = row - self.scroll_offset.y
        if 0 <= viewport_y < self.size.height:
            self.refresh(Region(0, viewport_y, self.size.width, 1))
