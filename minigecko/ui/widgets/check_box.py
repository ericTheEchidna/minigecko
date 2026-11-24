"""A check box that reads as ticked or not without relying on colour."""

from __future__ import annotations

from textual.content import Content
from textual.widgets import Checkbox


class CheckBox(Checkbox):
    """Textual's Checkbox drawn as ``[x]`` when on and ``[ ]`` when off.

    The stock widget shows the same X either way, only dimmer when off, which
    read as ticked (Eric, 2026-11-24).
    """

    DEFAULT_CSS = """
    CheckBox > .toggle--button { color: $text; background: transparent; }
    CheckBox.-on > .toggle--button { color: $text-success; background: transparent; text-style: bold; }
    """

    @property
    def _button(self) -> Content:
        style = self.get_visual_style("toggle--button")
        return Content.assemble(("[x]" if self.value else "[ ]", style))
