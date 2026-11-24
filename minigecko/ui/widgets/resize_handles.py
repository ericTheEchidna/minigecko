"""Drag handles: one resizes the action log, one splits the Data tab's panes."""

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


class HResizeHandle(Static):
    """Thin vertical divider between two side-by-side panes; drag left or right.

    The pane before it takes a percentage of the parent's width, so the split
    keeps its proportion when the terminal is resized. On release the app's
    ``save_jed_split(percent)`` stores it.
    """

    MIN_COLUMNS = 10  # neither pane gets narrower than this

    DEFAULT_CSS = """
    HResizeHandle {
        width: 1; height: 1fr;
        background: $panel-darken-2;
        color: $text-muted;
        content-align: center middle;
    }
    HResizeHandle:hover { background: $accent-darken-2; }
    """

    def __init__(self, left_id: str, **kwargs) -> None:
        super().__init__("┃", **kwargs)
        self._left_id = left_id
        self._dragging = False
        self._start_x = 0
        self._start_width = 0
        self.percent: float | None = None

    def on_mouse_down(self, event: MouseDown) -> None:
        self._dragging = True
        self._start_x = event.screen_x
        self._start_width = self.parent.query_one(f"#{self._left_id}").size.width
        self.capture_mouse()

    def on_mouse_move(self, event: MouseMove) -> None:
        if not self._dragging:
            return
        total = self.parent.size.width  # a % width is a share of the whole row
        room = total - self.size.width
        if room <= 2 * self.MIN_COLUMNS:
            return
        width = self._start_width + event.screen_x - self._start_x
        width = min(max(width, self.MIN_COLUMNS), room - self.MIN_COLUMNS)
        self.percent = round(100 * width / total, 1)
        self.parent.query_one(f"#{self._left_id}").styles.width = f"{self.percent}%"

    def on_mouse_up(self, _: MouseUp) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self.release_mouse()
        if self.percent is not None:
            self.app.save_jed_split(self.percent)  # type: ignore[attr-defined]
