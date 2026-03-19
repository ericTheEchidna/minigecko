"""Confirmation dialogs used by IC operations."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Checkbox, Label, Static


class WriteConfirmScreen(ModalScreen):
    """Write confirmation with optional verify-after-write checkbox."""

    DEFAULT_CSS = """
    WriteConfirmScreen { align: center middle; }
    WriteConfirmScreen > .confirm-container {
        width: 52; height: auto;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    WriteConfirmScreen .confirm-title { text-style: bold; color: $warning; margin-bottom: 1; }
    WriteConfirmScreen .confirm-msg   { margin-bottom: 1; }
    WriteConfirmScreen Checkbox        { margin-bottom: 1; }
    WriteConfirmScreen .confirm-detail { color: $error; margin-bottom: 1; }
    WriteConfirmScreen .confirm-hint  { color: $text-muted; }
    """

    BINDINGS = [
        Binding("enter", "confirm", "Confirm", priority=True),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, message: str, detail: str = "") -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._detail = detail

    def compose(self) -> ComposeResult:
        with Vertical(classes="confirm-container"):
            yield Label(self._title, classes="confirm-title")
            yield Label(self._message, classes="confirm-msg")
            if self._detail:
                yield Label(self._detail, classes="confirm-detail")
            yield Checkbox("Verify after write", value=True, id="chk-verify")
            yield Static("(Space) Toggle    (Enter) Confirm    (Esc) Cancel", classes="confirm-hint")

    def action_confirm(self) -> None:
        verify = self.query_one("#chk-verify", Checkbox).value
        self.dismiss(verify)

    def action_cancel(self) -> None:
        self.dismiss(None)


class EraseConfirmScreen(ModalScreen):
    """Erase confirmation with optional read-after-erase checkbox."""

    DEFAULT_CSS = """
    EraseConfirmScreen { align: center middle; }
    EraseConfirmScreen > .confirm-container {
        width: 52; height: auto;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }
    EraseConfirmScreen .confirm-title { text-style: bold; color: $error; margin-bottom: 1; }
    EraseConfirmScreen .confirm-msg   { margin-bottom: 1; }
    EraseConfirmScreen Checkbox        { margin-bottom: 1; }
    EraseConfirmScreen .confirm-hint  { color: $text-muted; }
    """

    BINDINGS = [
        Binding("enter", "confirm", "Confirm", priority=True),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(classes="confirm-container"):
            yield Label(self._title, classes="confirm-title")
            yield Label(self._message, classes="confirm-msg")
            yield Checkbox("Blank check after erase", value=True, id="chk-blank")
            yield Checkbox("Read after erase", value=False, id="chk-read")
            yield Static("(Space) Toggle    (Enter) Confirm    (Esc) Cancel", classes="confirm-hint")

    def action_confirm(self) -> None:
        blank_check = self.query_one("#chk-blank", Checkbox).value
        read_after = self.query_one("#chk-read", Checkbox).value
        self.dismiss((blank_check, read_after))

    def action_cancel(self) -> None:
        self.dismiss(None)
