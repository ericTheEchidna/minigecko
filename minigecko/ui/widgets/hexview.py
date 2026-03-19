"""Read-only hex + ASCII dump widget and modal screen."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

# Number of bytes per row in the hex dump.
_BYTES_PER_ROW = 16


def _header_line() -> str:
    """Column-header line whose spacing mirrors the data rows."""
    cols: list[str] = [f"{i:02X}" for i in range(_BYTES_PER_ROW)]
    cols.insert(8, "")  # mid-group gap matching data rows
    header_hex = " ".join(cols).ljust(3 * _BYTES_PER_ROW + 1)
    return f"{'Offset':8}  {header_hex} |{'0123456789ABCDEF'}|"


def _data_lines(data: bytes) -> list[str]:
    """Format *data* as classic hex+ASCII dump rows (no header)."""
    lines: list[str] = []
    for offset in range(0, len(data), _BYTES_PER_ROW):
        chunk = data[offset : offset + _BYTES_PER_ROW]

        hex_parts = []
        for i, b in enumerate(chunk):
            hex_parts.append(f"{b:02X}")
            if i == 7:
                hex_parts.append("")  # extra space between groups of 8
        hex_str = " ".join(hex_parts).ljust(3 * _BYTES_PER_ROW + 1)

        ascii_str = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)

        lines.append(f"{offset:08X}  {hex_str} |{ascii_str}|")
    return lines


class HexView(Vertical, can_focus=True):
    """Scrollable, read-only hex + ASCII dump of a binary file."""

    DEFAULT_CSS = """
    HexView {
        height: 1fr;
        padding: 0 1;
    }

    HexView > #hex-header {
        height: auto;
        width: auto;
    }

    HexView > #hex-body {
        height: 1fr;
        overflow-y: auto;
    }

    HexView > #hex-body > Static {
        width: auto;
    }
    """

    BINDINGS = [
        Binding("up", "scroll_up", "Up", show=False),
        Binding("down", "scroll_down", "Down", show=False),
        Binding("pageup", "page_up", "PgUp", show=False),
        Binding("pagedown", "page_down", "PgDn", show=False),
        Binding("home", "scroll_home", "Home", show=False),
        Binding("end", "scroll_end", "End", show=False),
    ]

    def __init__(
        self,
        path: Path,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._path = path

    def compose(self) -> ComposeResult:
        try:
            data = self._path.read_bytes()
        except OSError as exc:
            yield Static(f"[red]Cannot read file: {exc}[/red]")
            return

        if not data:
            yield Static("[dim]File is empty.[/dim]")
            return

        header = _header_line()
        separator = "─" * len(header)
        yield Static(f"{header}\n{separator}", id="hex-header")
        with ScrollableContainer(id="hex-body"):
            yield Static("\n".join(_data_lines(data)))

    def _body(self) -> ScrollableContainer:
        return self.query_one("#hex-body", ScrollableContainer)

    def action_scroll_up(self) -> None:
        self._body().scroll_up()

    def action_scroll_down(self) -> None:
        self._body().scroll_down()

    def action_page_up(self) -> None:
        self._body().scroll_page_up()

    def action_page_down(self) -> None:
        self._body().scroll_page_down()

    def action_scroll_home(self) -> None:
        self._body().scroll_home()

    def action_scroll_end(self) -> None:
        self._body().scroll_end()


class HexViewScreen(ModalScreen[None]):
    """Modal overlay wrapping a :class:`HexView`."""

    DEFAULT_CSS = """
    HexViewScreen {
        align: center middle;
    }

    #hexview-modal {
        width: 90%;
        height: 85%;
        border: heavy $accent;
        background: $surface;
        padding: 1 2;
    }

    #hexview-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #hexview-hint {
        color: $text-muted;
        margin-top: 1;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
    ]

    def __init__(self, path: Path, label: str | None = None) -> None:
        super().__init__()
        self._path = path
        self._label = label

    def compose(self) -> ComposeResult:
        label = self._label or "Hex View"
        title = f"── {label} ──────────────────────────────"
        with Vertical(id="hexview-modal"):
            yield Static(title, id="hexview-title")
            yield HexView(self._path, id="hexview-content")
            yield Static(
                "[dim]Esc[/dim] close   [dim]↑↓ PgUp PgDn Home End[/dim] scroll",
                id="hexview-hint",
            )