"""Main top toolbar widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static


class Toolbar(Horizontal):
    """Horizontal toolbar spanning the full width above main panels."""

    DEFAULT_CSS = """
    Toolbar {
        height: 2;
        background: $panel;
        border-bottom: solid $panel-darken-2;
        padding: 0 1;
        align: left middle;
    }
    Toolbar .tb-btn {
        padding: 0 1;
        color: $text;
        background: $panel-lighten-1;
    }
    Toolbar .tb-btn:hover { background: $accent-darken-2; color: $text; }
    Toolbar .tb-btn-disabled {
        padding: 0 1;
        color: $text-muted;
        background: $panel;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Selected IC: —", id="btn-select-ic", classes="tb-btn")
        yield Static("IC Ops [d]", id="btn-ic-ops", classes="tb-btn-disabled")
