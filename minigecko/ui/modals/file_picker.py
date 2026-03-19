"""File picker modal built on top of DirectoryTree."""

from __future__ import annotations

import time
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Footer, Label, Static


class FilePickerScreen(ModalScreen[Path | None]):
    """Modal file picker using DirectoryTree."""

    DEFAULT_CSS = """
    FilePickerScreen { align: center middle; }
    FilePickerScreen > .picker-container {
        width: 70; height: 30;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    FilePickerScreen #up-dir { color: $accent; margin-bottom: 0; }
    FilePickerScreen #up-dir:hover { color: $text; }
    FilePickerScreen #selected-label { color: $text-muted; margin-top: 1; }
    """

    BINDINGS = [
        Binding("enter", "confirm", "OK", priority=True),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, start_path: Path = Path.home()) -> None:
        super().__init__()
        self._root = start_path if start_path.is_dir() else start_path.parent
        self._selected: Path | None = None
        self._last_click_path: Path | None = None
        self._last_click_time: float = 0.0

    def compose(self) -> ComposeResult:
        with Vertical(classes="picker-container"):
            yield Static("↑  ..", id="up-dir")
            yield DirectoryTree(str(self._root), id="filetree")
            yield Label("", id="selected-label")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#filetree").focus()

    def on_static_clicked(self, event: Static.Clicked) -> None:  # type: ignore[attr-defined]
        if event.static.id == "up-dir":
            self._go_up()

    def _go_up(self) -> None:
        parent = self._root.parent
        if parent == self._root:
            return
        self._root = parent
        self._selected = None
        self.query_one("#selected-label", Label).update("")
        tree = self.query_one("#filetree", DirectoryTree)
        tree.path = self._root
        tree.focus()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = Path(event.path)
        now = time.monotonic()
        if path == self._last_click_path and (now - self._last_click_time) < 0.5:
            self.dismiss(path)
            return
        self._selected = path
        self._last_click_path = path
        self._last_click_time = now
        self.query_one("#selected-label", Label).update(str(self._selected))

    def action_confirm(self) -> None:
        if self._selected:
            self.dismiss(self._selected)
            return
        tree = self.query_one("#filetree", DirectoryTree)
        node = tree.cursor_node
        if node and node.data and not node.data.is_dir:
            self.dismiss(Path(node.data.path))

    def action_cancel(self) -> None:
        self.dismiss(None)
