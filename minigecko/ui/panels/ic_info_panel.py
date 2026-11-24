"""Selected chip information panel."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Link, Static

from minigecko.core.device_db import TYPE_EEPROM, TYPE_MCU, decode_flags

# Plain words for each set flag (keys from decode_flags). Unset flags are not shown.
_FEATURE_TEXT = {
    "can_erase":           "Erases electrically",
    "has_chip_id":         "Reports a chip ID, so Identify can confirm it",
    "word_size":           "16-bit data bus",
    "has_data_offset":     "Has a separate data memory",
    "off_protect_before":  "Write protect is cleared before writing",
    "protect_after":       "Write protect is set again after writing",
    "lock_bit_write_only": "Lock bits can be written but not read back",
    "has_calibration":     "Has calibration bytes",
    "reversed_package":    "Reversed package: check the socket diagram before seating",
    "can_adjust_vcc":      "Supply voltage can be set by hand",
    "can_adjust_vpp":      "Programming voltage can be set by hand",
}
_INTERFACE_TEXT = {
    "ZIF + ICSP": "Programs in the socket or in-circuit (ICSP)",
    "ICSP only":  "Programs in-circuit (ICSP) only",
    "Read-only":  "Read only: minipro cannot write it",
}
# Types where a missing chip ID is worth saying: Identify cannot confirm these.
_ID_EXPECTED_TYPES = {TYPE_EEPROM, TYPE_MCU}


def feature_lines(entry: dict) -> list[str]:
    """One plain line per flag that is set; nothing for flags that are not."""
    if not entry:
        return []
    lines: list[str] = []
    has_id = False
    for key, _label, value in decode_flags(entry):
        if key == "prog_support":
            if value in _INTERFACE_TEXT:
                lines.append(_INTERFACE_TEXT[value])
        elif value is True and key in _FEATURE_TEXT:
            lines.append(_FEATURE_TEXT[key])
            has_id = has_id or key == "has_chip_id"
    if not has_id and entry.get("type") in _ID_EXPECTED_TYPES:
        lines.append("No chip ID: Identify cannot confirm it")
    return [f"• {line}" for line in lines]


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
    ICInfoPanel #ic-desc       { color: $text; margin-bottom: 1; }
    ICInfoPanel #ic-flags      { margin-bottom: 1; }
    ICInfoPanel #ic-search-placeholder { margin-top: 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._current_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("No IC selected.", id="ic-name")
        yield Static("", id="ic-chip-info")
        yield Static("", id="ic-desc")
        yield Static("", id="ic-flags")
        yield Static("", id="ic-search-placeholder")

    def show(self, name: str) -> None:
        from minigecko.core import ddg_url, get_description, get_device

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

        desc = get_description(name)
        self.query_one("#ic-desc", Static).update(desc)

        self.query_one("#ic-flags", Static).update("\n".join(feature_lines(entry)))

        search_url = ddg_url(name)
        placeholder = self.query_one("#ic-search-placeholder", Static)
        placeholder.remove_children()
        placeholder.mount(Link("Find the datasheet", url=search_url, tooltip=search_url))
