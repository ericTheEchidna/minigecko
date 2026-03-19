"""Chip selection modal with category filter and quick search."""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, Label, ListItem, ListView, Static


class ChipSelectScreen(ModalScreen[str | None]):
    """Chip selection dialog with category filter and text search."""

    _CATEGORIES = [
        (0, "All"),
        (1, "ROM / EEPROM / Flash"),
        (2, "MCU"),
        (3, "PLD"),
        (4, "SRAM"),
        (5, "Logic"),
        (6, "NAND"),
        (7, "eMMC"),
        (8, "VGA"),
    ]

    DEFAULT_CSS = """
    ChipSelectScreen { align: center middle; }
    ChipSelectScreen > .cs-container {
        width: 70%; height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    ChipSelectScreen #cs-cats {
        height: 1; margin-bottom: 1;
    }
    ChipSelectScreen .cat-btn {
        width: auto; padding: 0 1; color: $text-muted; background: transparent;
    }
    ChipSelectScreen .cat-btn:hover { color: $text; }
    ChipSelectScreen .cat-active {
        width: auto; padding: 0 1; color: $accent; background: $panel-lighten-1;
    }
    ChipSelectScreen #cs-filter { margin-bottom: 1; }
    ChipSelectScreen #cs-list { height: 1fr; border: solid $panel; }
    ChipSelectScreen #cs-status { color: $text-muted; height: 1; margin-top: 1; }
    """

    BINDINGS = [
        Binding("enter", "confirm", "Select", priority=True),
        Binding("escape", "cancel", "Cancel"),
    ]

    _MAX_RESULTS = 200

    def __init__(self) -> None:
        super().__init__()
        self._all_devices: list[tuple[str, int]] = []
        self._filtered: list[str] = []
        self._category: int = 0
        self._last_click_idx: int | None = None
        self._last_click_time: float = 0.0

    def compose(self) -> ComposeResult:
        with Vertical(classes="cs-container"):
            with Horizontal(id="cs-cats"):
                for type_id, label in self._CATEGORIES:
                    cls = "cat-active" if type_id == 0 else "cat-btn"
                    yield Static(label, id=f"cat-{type_id}", classes=cls)
            yield Input(placeholder="Type to search…", id="cs-filter")
            yield ListView(id="cs-list")
            yield Static("", id="cs-status")
        yield Footer()

    def on_mount(self) -> None:
        from minigecko.core import get_db

        db = get_db()
        self._all_devices = sorted((name, entry["type"]) for name, entry in db.items())
        total = len(self._all_devices)
        self.query_one("#cs-status", Static).update(f"{total:,} devices — type to search")
        self.query_one("#cs-filter", Input).focus()

    def on_click(self, event) -> None:
        widget_id = getattr(event.widget, "id", None) or ""
        if not widget_id.startswith("cat-"):
            return
        try:
            type_id = int(widget_id[4:])
        except ValueError:
            return
        self._set_category(type_id)

    def _set_category(self, type_id: int) -> None:
        for tid, _ in self._CATEGORIES:
            btn = self.query_one(f"#cat-{tid}", Static)
            btn.set_classes("cat-active" if tid == type_id else "cat-btn")
        self._category = type_id
        self._refilter()

    def _candidates(self) -> list[str]:
        if self._category == 0:
            return [name for name, _ in self._all_devices]
        return [name for name, t in self._all_devices if t == self._category]

    def _refilter(self) -> None:
        q = self.query_one("#cs-filter", Input).value.strip().upper()
        candidates = self._candidates()
        matched = [n for n in candidates if q in n.upper()] if q else candidates
        self._fill_list(matched)
        shown = len(self._filtered)
        total = len(matched)
        cat_total = len(candidates)
        suffix = f"  (showing {shown} of {total})" if total > shown else ""
        cat_label = "" if self._category == 0 else f"{self._CATEGORIES[self._category][1]}  "
        self.query_one("#cs-status", Static).update(
            f"{cat_label}{total:,} match{'es' if total != 1 else ''}{suffix}"
            if q
            else f"{cat_label}{cat_total:,} devices"
        )

    def _fill_list(self, names: list[str]) -> None:
        self._filtered = names[:self._MAX_RESULTS]
        lv = self.query_one("#cs-list", ListView)
        lv.clear()
        for name in self._filtered:
            lv.append(ListItem(Label(name)))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one("#cs-list", ListView).index
        now = time.monotonic()
        if idx == self._last_click_idx and (now - self._last_click_time) < 0.5:
            self.action_confirm()
            return
        self._last_click_idx = idx
        self._last_click_time = now

    def on_input_changed(self, event: Input.Changed) -> None:
        self._refilter()
        lv = self.query_one("#cs-list", ListView)
        if self._filtered:
            lv.index = 0

    def on_key(self, event) -> None:
        if not self.query_one("#cs-filter", Input).has_focus:
            return
        lv = self.query_one("#cs-list", ListView)
        if not self._filtered:
            return
        if event.key == "down":
            idx = lv.index
            lv.index = min((idx or 0) + 1, len(self._filtered) - 1)
            event.prevent_default()
        elif event.key == "up":
            idx = lv.index
            if idx is not None and idx > 0:
                lv.index = idx - 1
            event.prevent_default()

    def action_confirm(self) -> None:
        lv = self.query_one("#cs-list", ListView)
        idx = lv.index
        if idx is not None and 0 <= idx < len(self._filtered):
            self.dismiss(self._filtered[idx])
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
