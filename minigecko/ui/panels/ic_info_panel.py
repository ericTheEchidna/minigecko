"""Selected chip information panel."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Link, Static


class ICInfoPanel(VerticalScroll):
    """Right panel showing info about the selected IC."""

    DEFAULT_CSS = """
    ICInfoPanel {
        width: 1fr;
        height: 18;
        background: $surface;
        padding: 1 2;
    }
    ICInfoPanel #ic-name       { text-style: bold; color: $accent; }
    ICInfoPanel #ic-chip-info  { color: $text-muted; margin-bottom: 1; }
    ICInfoPanel #ic-flags      { margin-bottom: 1; }
    ICInfoPanel #ic-search-placeholder { margin-top: 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._current_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("No IC selected.", id="ic-name")
        yield Static("", id="ic-chip-info")
        yield Static("", id="ic-flags")
        yield Static("", id="ic-search-placeholder")

    def show(self, name: str) -> None:
        from rich.table import Table
        from minigecko.core import ddg_url, decode_flags, get_device

        self._current_name = name
        entry = get_device(name) or {}

        self.query_one("#ic-name", Static).update(name)

        parts = []
        if entry.get("type_label"):
            parts.append(entry["type_label"])
        if entry.get("size_label"):
            parts.append(entry["size_label"])
        if entry.get("package"):
            parts.append(entry["package"])
        if entry.get("pin_count"):
            parts.append(f"{entry['pin_count']} pins")
        if entry.get("is_isp"):
            parts.append("ISP")
        self.query_one("#ic-chip-info", Static).update("  ·  ".join(parts))

        flags_widget = self.query_one("#ic-flags", Static)
        if entry:
            bools = [(desc, value) for _k, desc, value in decode_flags(entry) if isinstance(value, bool)]
            strings = [(desc, value) for _k, desc, value in decode_flags(entry) if not isinstance(value, bool)]

            t = Table(box=None, show_header=False, padding=(0, 1), expand=False)
            t.add_column(no_wrap=True, min_width=1)
            t.add_column(no_wrap=True, min_width=16)
            t.add_column(no_wrap=True, min_width=1)
            t.add_column(no_wrap=True, min_width=16)

            pairs = list(zip(bools[0::2], bools[1::2]))
            for (d1, v1), (d2, v2) in pairs:
                t.add_row(
                    f"[{'green' if v1 else 'red'}]{'✔' if v1 else '✘'}[/]", d1,
                    f"[{'green' if v2 else 'red'}]{'✔' if v2 else '✘'}[/]", d2,
                )
            if len(bools) % 2:
                d1, v1 = bools[-1]
                t.add_row(f"[{'green' if v1 else 'red'}]{'✔' if v1 else '✘'}[/]", d1, "", "")
            for desc, value in strings:
                t.add_row("[dim]▸[/]", f"{desc}:  [yellow]{value}[/]", "", "")

            flags_widget.update(t)
        else:
            flags_widget.update("")

        search_url = ddg_url(name)
        placeholder = self.query_one("#ic-search-placeholder", Static)
        placeholder.remove_children()
        placeholder.mount(Link(search_url, url=search_url))
