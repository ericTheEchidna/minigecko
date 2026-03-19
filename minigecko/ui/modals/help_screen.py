"""Help screen — renders the user manual via MarkdownViewer."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import MarkdownViewer

_MANUAL_PATH = Path(__file__).parent.parent.parent / "data" / "user-manual.md"


class HelpScreen(ModalScreen[None]):
    """Full-screen modal displaying the MiniGecko user manual."""

    DEFAULT_CSS = """
    HelpScreen { align: center middle; }
    HelpScreen > MarkdownViewer {
        width: 90%;
        height: 90%;
        border: thick $primary;
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Close", show=True),
    ]

    def compose(self) -> ComposeResult:
        try:
            text = _MANUAL_PATH.read_text()
        except OSError:
            text = "_User manual not found._"
        yield MarkdownViewer(text, show_table_of_contents=True)
