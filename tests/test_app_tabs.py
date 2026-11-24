"""Main screen: Chip and Data tabs follow the last action; the log sits under both."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import TabbedContent, TextArea

from minigecko.core import emulator
from minigecko.core import minipro
from minigecko.ui import app_shell
from minigecko.ui.app_shell import MinigeckoApp
from minigecko.ui.panels import ActionLogPanel, HexPanel

JED = Path(__file__).parent / "data" / "jed" / "counter_16v8.jed"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(minipro, "_transport", emulator.emulate)  # never the real programmer
    monkeypatch.setattr(app_shell, "_save_state", lambda state: None)  # never the real state file
    return MinigeckoApp()


def _load(app: MinigeckoApp, path: Path) -> None:
    app._file_label, app._data_path, app._read_from = str(path), path, None
    app._load_hex(path)


async def test_tabs_follow_the_last_action(app, tmp_path):
    rom = tmp_path / "rom.bin"
    rom.write_bytes(bytes(range(256)))
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        tabs = app.query_one("#main-tabs", TabbedContent)
        assert tabs.active == "tab-chip"

        _load(app, rom)
        await pilot.pause(0.3)
        assert tabs.active == "tab-data"
        assert app.query_one(HexPanel).display and not app.query_one("#jed-pair").display

        app._set_selected_ic("7410")
        await pilot.pause(0.1)
        assert tabs.active == "tab-chip"

        await pilot.press("2")
        assert tabs.active == "tab-data"
        await pilot.press("1")
        assert tabs.active == "tab-chip"


async def test_jed_shows_as_text(app):
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _load(app, JED)
        await pilot.pause(0.3)
        jed = app.query_one("#jed-view", TextArea)
        assert app.query_one("#jed-pair").display and not app.query_one(HexPanel).display
        assert "*QF2194" in jed.text and "\x02" not in jed.text


async def test_log_is_outside_the_tabs(app):
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        log = app.query_one(ActionLogPanel)
        assert not any(isinstance(a, TabbedContent) for a in log.ancestors)


async def test_jed_shows_equations_beside_the_fuse_map(app, monkeypatch):
    from minigecko.core import jedec
    monkeypatch.setattr(jedec, "decompile", lambda path, chip="": ("Equations:\n\nX = A", "note."))
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _load(app, JED)
        await pilot.pause(0.3)
        assert "X = A" in app.query_one("#jed-eqn", TextArea).text
        assert "*QF2194" in app.query_one("#jed-view", TextArea).text
