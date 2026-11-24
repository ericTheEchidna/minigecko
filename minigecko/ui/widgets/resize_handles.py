"""Drag handle that resizes the action log under the main tabs."""

from __future__ import annotations

from textual.events import MouseDown, MouseMove, MouseUp
from textual.widgets import Static


class VResizeHandle(Static):
    """Thin horizontal divider above the action log; drag up to enlarge the log."""

    DEFAULT_CSS = """
    VResizeHandle {
        width: 1fr; height: 1;
        background: $panel-darken-2;
        color: $text-muted;
        content-align: center middle;
    }
    VResizeHandle:hover { background: $accent-darken-2; }
    """

    def __init__(self) -> None:
        super().__init__("━")
        self._dragging = False
        self._start_y = 0
        self._start_height = 0

    def on_mouse_down(self, event: MouseDown) -> None:
        self._dragging = True
        self._start_y = event.screen_y
        panel = self.app.query_one("ActionLogPanel")
        self._start_height = panel.styles.height.value  # type: ignore[union-attr]
        self.capture_mouse()

    def on_mouse_move(self, event: MouseMove) -> None:
        if not self._dragging:
            return
        delta = event.screen_y - self._start_y
        new_height = max(4, int(self._start_height - delta))
        self.app.query_one("ActionLogPanel").styles.height = new_height

    def on_mouse_up(self, _: MouseUp) -> None:
        self._dragging = False
        self.release_mouse()
        self.app.save_log_height()  # type: ignore[attr-defined]
