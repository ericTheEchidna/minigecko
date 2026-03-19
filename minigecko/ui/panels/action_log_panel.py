"""Action log with operation progress bar."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import ProgressBar, RichLog, Static


class ActionLogPanel(Vertical):
    """Bottom-right panel, scrollable log of hardware operations."""

    DEFAULT_CSS = """
    ActionLogPanel {
        height: 1fr;
        border-top: solid $panel-darken-2;
    }
    ActionLogPanel #log-title {
        background: $panel;
        color: $text-muted;
        padding: 0 1;
        height: 1;
    }
    ActionLogPanel RichLog {
        height: 1fr;
        padding: 0 1;
    }
    ActionLogPanel ProgressBar {
        height: 1;
        margin: 0 1;
        display: none;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._messages: list[str] = []

    def compose(self) -> ComposeResult:
        yield Static("Action Log", id="log-title")
        yield RichLog(id="action-log", highlight=False, markup=True, auto_scroll=True, wrap=True)
        yield ProgressBar(total=100, show_eta=False, show_percentage=True, id="op-progress")

    def show_progress(self, percent: int | None) -> None:
        bar = self.query_one("#op-progress", ProgressBar)
        bar.display = True
        if percent is not None:
            bar.update(progress=percent)

    def hide_progress(self) -> None:
        bar = self.query_one("#op-progress", ProgressBar)
        bar.display = False
        bar.update(progress=0)

    def on_resize(self) -> None:
        self.set_timer(0.05, self._reflow)

    def _reflow(self) -> None:
        widget = self.query_one("#action-log", RichLog)
        width = widget.scrollable_content_region.width
        if width <= 0:
            return
        widget.clear()
        for msg in self._messages:
            widget.write(msg, width=width, scroll_end=False)
        widget.scroll_end(animate=False)

    def log(self, message: str) -> None:
        from datetime import datetime

        ts = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{ts}]  {message}"
        self._messages.append(formatted)
        self.query_one("#action-log", RichLog).write(formatted)
