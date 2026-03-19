"""Drag handles used to resize main layout panels."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.events import MouseDown, MouseMove, MouseUp
from textual.widgets import Static

from minigecko.ui.panels import HexPanel, ICInfoPanel

if TYPE_CHECKING:
    from minigecko.ui.app_shell import MinigeckoApp


class ResizeHandle(Static):
    """Thin draggable divider for resizing the hex panel."""

    DEFAULT_CSS = """
    ResizeHandle {
        width: 1; height: 1fr;
        background: $panel-darken-2;
        color: $text-muted;
        content-align: center middle;
    }
    ResizeHandle:hover { background: $accent-darken-2; }
    """

    def __init__(self) -> None:
        super().__init__("┃")
        self._dragging = False
        self._start_x = 0
        self._start_width = 0

    def on_mouse_down(self, event: MouseDown) -> None:
        self._dragging = True
        self._start_x = event.screen_x
        panel = self.app.query_one(HexPanel)
        self._start_width = panel.styles.width.value  # type: ignore[union-attr]
        self.capture_mouse()

    def on_mouse_move(self, event: MouseMove) -> None:
        if not self._dragging:
            return
        delta = event.screen_x - self._start_x
        new_width = max(20, int(self._start_width + delta))
        self.app.query_one(HexPanel).styles.width = new_width

    def on_mouse_up(self, _: MouseUp) -> None:
        self._dragging = False
        self.release_mouse()
        app = self.app
        assert isinstance(app, MinigeckoApp)
        app.save_panel_width()


class VResizeHandle(Static):
    """Thin horizontal divider between IC info and action log."""

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
        panel = self.app.query_one(ICInfoPanel)
        self._start_height = panel.styles.height.value  # type: ignore[union-attr]
        self.capture_mouse()

    def on_mouse_move(self, event: MouseMove) -> None:
        if not self._dragging:
            return
        delta = event.screen_y - self._start_y
        new_height = max(4, int(self._start_height + delta))
        self.app.query_one(ICInfoPanel).styles.height = new_height

    def on_mouse_up(self, _: MouseUp) -> None:
        self._dragging = False
        self.release_mouse()
        app = self.app
        assert isinstance(app, MinigeckoApp)
        app.save_info_panel_height()
