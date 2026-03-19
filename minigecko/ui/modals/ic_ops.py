"""IC operation menu and chip-type inference helpers."""

from __future__ import annotations

import re as _re
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Label, Static

from minigecko.ui.modals.confirmations import EraseConfirmScreen, WriteConfirmScreen
from minigecko.ui.modals.file_picker import FilePickerScreen

_PIN = ("pin_check", "Pin Check", False)
_TEST = ("logic_test", "RAM / Logic Test", False)
_READ = ("read", "Read from device", False)
_WDEV = ("write_device", "Write to device", False)
_WFILE = ("write_file", "Write to file", False)
_BLANK = ("blank_check", "Blank Check", False)
_ERASE = ("erase", "Erase", False)
_CMP = ("compare", "Compare vs file…", False)

_OPS_BY_TYPE: dict[int, list] = {
    1: [_PIN, _READ, _WDEV, _WFILE, _BLANK, _ERASE, _CMP],
    2: [_PIN, _READ, _WDEV, _WFILE, _BLANK, _ERASE, _CMP],
    3: [_PIN, _READ, _WDEV, _BLANK, _ERASE],
    4: [_TEST],
    5: [_TEST],
    6: [_PIN, _READ, _WDEV, _WFILE, _BLANK, _ERASE, _CMP],
    7: [_PIN, _READ, _WDEV, _WFILE],
    8: [_PIN, _READ, _WDEV, _WFILE],
}
_OPS_DEFAULT = _OPS_BY_TYPE[1]

_LOGIC_PATTERN = _re.compile(r"^[A-Za-z]{0,4}(74|54|40|45|47)[A-Za-z]*\d", _re.IGNORECASE)
_SRAM_PATTERN = _re.compile(r"^[A-Za-z]{0,4}(62\d{2,3}|61[CL]\d{2,3}|7[Cc]\d{3}|55\d{2}|43\d{2})", _re.IGNORECASE)


def infer_chip_type(name: str) -> int:
    """Best-effort chip-type guess when the device is not in the DB."""
    n = name.strip()
    if _LOGIC_PATTERN.match(n):
        return 5
    if _SRAM_PATTERN.match(n):
        return 4
    return 1


class ICOpsScreen(ModalScreen[None]):
    """IC operations menu dynamically filtered by chip type."""

    DEFAULT_CSS = """
    ICOpsScreen { align: center middle; }
    ICOpsScreen > .ops-container {
        width: 50; height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    ICOpsScreen Label.ops-title {
        text-style: bold; color: $accent; margin-bottom: 1;
    }
    ICOpsScreen .ops-btn {
        padding: 0 1; margin-bottom: 0;
        color: $text; background: $panel-lighten-1;
    }
    ICOpsScreen .ops-btn:hover { background: $accent-darken-2; color: $text; }
    ICOpsScreen .ops-btn-active { padding: 0 1; margin-bottom: 0; color: $text; background: $accent-darken-2; }
    ICOpsScreen .ops-disabled { color: $text-muted; background: transparent; }
    ICOpsScreen #ops-status { color: $text-muted; margin-top: 1; height: 1; }
    """

    BINDINGS = [
        ("escape", "dismiss(None)", "Cancel"),
        ("up", "move(-1)", "Up"),
        ("down", "move(1)", "Down"),
        ("enter", "activate", "Select"),
    ]

    def __init__(self, ic_name: str, chip_type: int = 1, is_isp: bool = False, can_erase: bool = True) -> None:
        super().__init__()
        self._ic_name = ic_name
        self._cursor: int = 0
        self._ops = list(_OPS_BY_TYPE.get(chip_type, _OPS_DEFAULT))
        if not can_erase and any(op_id == "erase" for op_id, _, _ in self._ops):
            result = []
            for op_id, label, disabled in self._ops:
                if op_id == "erase":
                    result.append((op_id, label, True))
                    result.append(("_uv_note", "⚠  UV erase only (not electrical)", True))
                else:
                    result.append((op_id, label, disabled))
            self._ops = result
        if is_isp:
            self._ops.append(("_isp_note", "⚡  ISP-capable device", True))

    def compose(self) -> ComposeResult:
        with Vertical(classes="ops-container"):
            yield Label(f"IC Ops: {self._ic_name}", classes="ops-title")
            for op_id, label, disabled in self._ops:
                if disabled:
                    yield Static(f"  {label}", classes="ops-disabled")
                else:
                    yield Static(label, id=f"op-{op_id}", classes="ops-btn")
            yield Static("", id="ops-status")
        yield Footer()

    def _actionable_ids(self) -> list[str]:
        """Return widget IDs of non-disabled ops in order."""
        return [f"op-{op_id}" for op_id, _, disabled in self._ops if not disabled]

    def _update_highlight(self) -> None:
        ids = self._actionable_ids()
        for i, wid in enumerate(ids):
            w = self.query_one(f"#{wid}", Static)
            w.set_classes("ops-btn-active" if i == self._cursor else "ops-btn")

    def on_mount(self) -> None:
        self._cursor = 0
        self._update_highlight()

    def action_move(self, delta: int) -> None:
        ids = self._actionable_ids()
        if not ids:
            return
        self._cursor = max(0, min(self._cursor + delta, len(ids) - 1))
        self._update_highlight()

    def action_activate(self) -> None:
        ids = self._actionable_ids()
        if not ids or self._cursor >= len(ids):
            return
        self._dispatch_op(ids[self._cursor])

    def on_click(self, event) -> None:
        widget_id = getattr(event.widget, "id", None) or ""
        if widget_id.startswith("op-"):
            self._dispatch_op(widget_id)

    def _dispatch_op(self, widget_id: str) -> None:
        if widget_id == "op-pin_check":
            self.dismiss(None)
            self.app.run_pin_check_op(self._ic_name)
        elif widget_id == "op-logic_test":
            self.dismiss(None)
            self.app.run_logic_test_op(self._ic_name)
        elif widget_id == "op-read":
            self.dismiss(None)
            self.app.run_read_op(self._ic_name)
        elif widget_id == "op-write_device":
            def _on_write_confirmed(result) -> None:
                if result is None:
                    return
                self.dismiss(None)
                self.app.run_write_to_device_op(self._ic_name, verify_after=result)

            src_name = self.app.get_write_source_label()
            self.app.push_screen(
                WriteConfirmScreen(
                    f"Write to {self._ic_name}?",
                    f"Source: {src_name}",
                    detail="WARNING: This will OVERWRITE the device. Cannot be undone.",
                ),
                _on_write_confirmed,
            )
        elif widget_id == "op-write_file":
            self.dismiss(None)
            self.app.run_write_to_file_op()
        elif widget_id == "op-blank_check":
            self.dismiss(None)
            self.app.run_blank_check_op(self._ic_name)
        elif widget_id == "op-compare":
            def _on_compare_file(ref: Path | None) -> None:
                if ref:
                    self.dismiss(None)
                    self.app.run_compare_op(self._ic_name, ref)

            self.app.push_screen(
                FilePickerScreen(start_path=self.app.get_last_directory()),
                _on_compare_file,
            )
        elif widget_id == "op-erase":
            def _on_erase_confirmed(result) -> None:
                if result is None:
                    return
                blank_check, read_after = result
                self.dismiss(None)
                self.app.run_erase_op(self._ic_name, blank_check_after=blank_check, read_after=read_after)

            self.app.push_screen(
                EraseConfirmScreen(
                    f"Erase {self._ic_name}?",
                    "This will permanently erase all device contents.",
                ),
                _on_erase_confirmed,
            )
