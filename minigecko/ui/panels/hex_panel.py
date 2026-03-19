"""Hex dump panel widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Static

from minigecko.ui.hexdump import _HEX_WIDTH, _col_header_markup, _separator_markup
from minigecko.ui.widgets.hex_dump_view import HexDumpView


class HexPanel(Vertical):
    """Left panel showing a hex dump of the loaded file."""

    DEFAULT_CSS = """
    HexPanel {
        width: 66; height: 1fr;
        background: $surface;
        border-right: solid $panel-darken-2;
        padding: 0 1;
    }
    HexPanel > #hex-header-row {
        height: 1;
    }
    HexPanel > #hex-header-row > #hex-offset-input {
        width: 10;
        height: 1;
        border: none;
        padding: 0;
        background: transparent;
        color: cyan;
        text-style: bold;
    }
    HexPanel > #hex-header-row > #hex-col-labels {
        height: 1;
        width: auto;
    }
    HexPanel > #hex-separator {
        height: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="hex-header-row"):
            yield Input(placeholder="offset", id="hex-offset-input")
            yield Static(_col_header_markup(), id="hex-col-labels")
        yield Static(_separator_markup(), id="hex-separator")
        yield HexDumpView(id="hex-log")

    def on_mount(self) -> None:
        self._set_header_visible(False)

    def _set_header_visible(self, visible: bool) -> None:
        self.query_one("#hex-header-row").display = visible
        self.query_one("#hex-separator").display = visible

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip().lower().removeprefix("0x")
        try:
            offset = int(raw, 16)
        except ValueError:
            return
        self.query_one(HexDumpView).jump_to_offset(offset)
        event.input.blur()

    def load(self, data: bytes) -> None:
        self._set_header_visible(True)
        self.query_one(HexDumpView).load(data)

    def clear(self) -> None:
        self._set_header_visible(False)
        self.query_one(HexDumpView).clear()

    def scroll_top(self) -> None:
        self.query_one(HexDumpView).scroll_home(animate=False)
