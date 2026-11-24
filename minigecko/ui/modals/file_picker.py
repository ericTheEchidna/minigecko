"""File picker modal built on top of DirectoryTree: open an existing file, or name one to save."""

from __future__ import annotations

import time
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Footer, Input, Label, Static


class FilePickerScreen(ModalScreen[Path | None]):
    """Modal file picker using DirectoryTree.

    With *save_name* set it is a save dialog: the tree picks the folder, the
    input names the file, and an existing file needs a second Enter.
    """

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
    FilePickerScreen #picker-title { text-style: bold; }
    """

    BINDINGS = [
        Binding("enter", "confirm", "OK", priority=True),
        Binding("escape", "cancel", "Cancel"),
        # Not priority: in the save dialog's name box Backspace still edits text.
        Binding("backspace", "go_up", "Up a folder"),
    ]

    def __init__(self, start_path: Path = Path.home(), save_name: str | None = None) -> None:
        super().__init__()
        self._root = start_path if start_path.is_dir() else start_path.parent
        self._save_name = save_name
        self._save_dir = self._root
        self._overwrite_ok: Path | None = None
        self._selected: Path | None = None
        self._last_click_path: Path | None = None
        self._last_click_time: float = 0.0

    def compose(self) -> ComposeResult:
        with Vertical(classes="picker-container"):
            yield Static("Save as" if self._saving else "Open file", id="picker-title")
            yield Static(self._up_label(), id="up-dir")
            yield DirectoryTree(str(self._root), id="filetree")
            if self._saving:
                yield Input(self._save_name or "", placeholder="File name", id="save-name")
            yield Label(self._save_hint(), id="selected-label")
        yield Footer()

    @property
    def _saving(self) -> bool:
        return self._save_name is not None

    def _save_hint(self) -> str:
        return f"Folder: {self._save_dir}" if self._saving else ""

    def on_mount(self) -> None:
        self.query_one("#save-name" if self._saving else "#filetree").focus()

    def _up_label(self) -> str:
        return f"↑ Up a folder (Backspace)    {self._root}"

    def on_click(self, event) -> None:
        if getattr(event.widget, "id", None) == "up-dir":
            self._go_up()

    def action_go_up(self) -> None:
        self._go_up()

    def _go_up(self) -> None:
        parent = self._root.parent
        if parent == self._root:
            return
        self._root = parent
        self._save_dir = parent
        self.query_one("#up-dir", Static).update(self._up_label())
        self._selected = None
        self.query_one("#selected-label", Label).update(self._save_hint())
        tree = self.query_one("#filetree", DirectoryTree)
        tree.path = self._root
        tree.focus()

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        if self._saving:
            self._save_dir = Path(event.path)
            self.query_one("#selected-label", Label).update(self._save_hint())

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = Path(event.path)
        if self._saving:
            self._save_dir = path.parent
            self.query_one("#save-name", Input).value = path.name
            self.query_one("#selected-label", Label).update(self._save_hint())
            return
        now = time.monotonic()
        if path == self._last_click_path and (now - self._last_click_time) < 0.5:
            self.dismiss(path)
            return
        self._selected = path
        self._last_click_path = path
        self._last_click_time = now
        self.query_one("#selected-label", Label).update(str(self._selected))

    def action_confirm(self) -> None:
        if self._saving:
            self._confirm_save()
            return
        if self._selected:
            self.dismiss(self._selected)
            return
        tree = self.query_one("#filetree", DirectoryTree)
        node = tree.cursor_node
        if node and node.data and not Path(node.data.path).is_dir():
            self.dismiss(Path(node.data.path))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _confirm_save(self) -> None:
        tree = self.query_one("#filetree", DirectoryTree)
        if tree.has_focus:  # Enter in the tree picks a folder or a name, it doesn't save
            node = tree.cursor_node
            if node and node.data:
                path = Path(node.data.path)
                if path.is_dir():
                    self._save_dir = path
                else:
                    self._save_dir = path.parent
                    self.query_one("#save-name", Input).value = path.name
                self.query_one("#selected-label", Label).update(self._save_hint())
            self.query_one("#save-name", Input).focus()
            return
        name = self.query_one("#save-name", Input).value.strip()
        if not name:
            self.query_one("#selected-label", Label).update("Type a file name first.")
            return
        target = self._save_dir / name
        if target.is_dir():
            self.query_one("#selected-label", Label).update(f"{name} is a folder.")
            return
        if target.exists() and self._overwrite_ok != target:
            self._overwrite_ok = target
            self.query_one("#selected-label", Label).update(
                f"{target} already exists. Press Enter again to overwrite it."
            )
            return
        self.dismiss(target)
