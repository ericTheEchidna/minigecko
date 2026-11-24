"""Main screen: Chip and Data tabs follow the last action; the log sits under both."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Static, TabbedContent, TextArea

from minigecko.core import emulator
from minigecko.core import minipro
from minigecko.ui import app_shell
from minigecko.ui.app_shell import MinigeckoApp
from minigecko.ui.panels import ActionLogPanel, HexPanel
from minigecko.ui.state import _DEFAULT_STATE

JED = Path(__file__).parent / "data" / "jed" / "counter_16v8.jed"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(minipro, "_transport", emulator.emulate)  # never the real programmer
    monkeypatch.setattr(app_shell, "_save_state", lambda state: None)  # never the real state file
    monkeypatch.setattr(app_shell, "_load_state", lambda: dict(_DEFAULT_STATE))  # nor its values
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
        assert app.query_one("#jed-eqn", TextArea).text == "Equations:\n\nX = A"  # no note in it
        assert "note." in str(app.query_one("#eqn-title", Static).render())
        assert "*QF2194" in app.query_one("#jed-view", TextArea).text


async def test_dragging_the_divider_resizes_the_jed_panes(app, monkeypatch):
    saved: list[dict] = []
    monkeypatch.setattr(app_shell, "_save_state", lambda state: saved.append(dict(state)))
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _load(app, JED)
        await pilot.pause(0.3)
        left = app.query_one("#jed-left")
        right = app.query_one("#jed-eqn").parent
        before = left.size.width
        assert abs(before - right.size.width) <= 2  # starts at half and half

        await pilot.mouse_down("#jed-split")
        await pilot.hover("#jed-split", offset=(-30, 0))
        await pilot.mouse_up("#jed-split")  # the handle has moved with the drag
        await pilot.pause(0.2)

        assert left.size.width == before - 30
        assert right.size.width > before + 25
        assert saved and saved[-1]["jed_split"] < 30  # remembered as a share of the width
        assert left.styles.width.value == saved[-1]["jed_split"]


async def test_pld_shows_source_beside_its_jeds_equations(app, monkeypatch, tmp_path):
    from minigecko.core import jedec
    opened: list[Path] = []

    def fake(path, chip=""):
        opened.append(path)
        return ("Equations:\n\nPAGE_CK = WR", "Decompiled.")

    monkeypatch.setattr(jedec, "decompile", fake)
    pld = JED.parent / "forbin80_mem.pld"
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _load(app, pld)
        await pilot.pause(0.3)
        assert app.query_one("#jed-pair").display and not app.query_one(HexPanel).display
        assert "Device   g22v10" in app.query_one("#jed-view", TextArea).text
        assert "PAGE_CK = WR" in app.query_one("#jed-eqn", TextArea).text
        assert opened == [pld.with_suffix(".jed")]

        lone = tmp_path / "lone.pld"
        lone.write_text("GAL16V8\nLone\n")
        _load(app, lone)
        await pilot.pause(0.3)
        assert "GAL16V8" in app.query_one("#jed-view", TextArea).text
        assert "No lone.jed beside lone.pld" in app.query_one("#jed-eqn", TextArea).text


async def test_chp_shows_pinout_beside_its_jeds_equations(app, monkeypatch):
    from minigecko.core import jedec
    monkeypatch.setattr(jedec, "decompile", lambda path, chip="": ("Equations:\n\no12 = i2", "ok."))
    chp = JED.parent / "gates_16v8.chp"
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _load(app, chp)
        await pilot.pause(0.3)
        assert "Pinout (gates_16v8.chp)" in str(app.query_one("#jed-title", Static).render())
        shown = app.query_one("#jed-view", TextArea).text
        assert "-------\\___/-------" in shown
        lines = [ln for ln in shown.splitlines() if ln.strip()]
        assert min(len(ln) - len(ln.lstrip()) for ln in lines) == 2  # Galette's margin trimmed
        assert "o12 = i2" in app.query_one("#jed-eqn", TextArea).text
        assert app.query_one("#jed-right").display


async def test_plain_text_fills_the_tab_and_binary_stays_hex(app, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("Socket the GAL notch up.\n\tPin 1 is the clock.\n")
    rom = tmp_path / "rom.bin"
    rom.write_bytes(bytes([0x00, 0xFF, 0x41, 0x42]) * 64)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _load(app, notes)
        await pilot.pause(0.3)
        assert app.query_one("#jed-pair").display and not app.query_one(HexPanel).display
        assert app.query_one("#jed-view", TextArea).text.startswith("Socket the GAL")
        assert not app.query_one("#jed-right").display
        assert not app.query_one("#jed-split").display
        assert app.query_one("#jed-left").size.width > 110  # the whole tab

        _load(app, rom)
        await pilot.pause(0.3)
        assert app.query_one(HexPanel).display and not app.query_one("#jed-pair").display

        _load(app, JED)  # a .jed after plain text gets its split back
        await pilot.pause(0.5)
        assert app.query_one("#jed-right").display and app.query_one("#jed-split").display
        assert abs(app.query_one("#jed-left").size.width - 60) <= 2


def test_text_detection():
    from minigecko.ui.app_shell import _as_text
    assert _as_text(b"GAL16V8\r\nGates\n") == "GAL16V8\r\nGates\n"
    assert _as_text("Pinout — µs\n".encode()) is not None  # UTF-8 is text
    assert _as_text(b"\x02*QF2194*\x03") is not None  # JEDEC framing
    assert _as_text(b"") is None
    assert _as_text(b"AB\x00CD") is None  # zero byte
    assert _as_text(b"\xff\xff\xff\xff") is None  # erased EPROM: not UTF-8
    assert _as_text(b"\x1b[0mhello") is None  # other control bytes


async def test_edit_a_pld_and_save_it_in_place(app, tmp_path):
    pld = tmp_path / "gates.pld"
    pld.write_text("GAL16V8\nGates\n")
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _load(app, pld)
        await pilot.pause(0.3)
        view = app.query_one("#jed-view", TextArea)
        assert not view.read_only and view.show_line_numbers

        await pilot.press("ctrl+s")  # nothing changed yet: the file is untouched
        assert pld.read_text() == "GAL16V8\nGates\n"

        view.insert("; bench copy\n", (0, 0))
        assert app._unsaved()
        await pilot.press("ctrl+s")
        await pilot.pause(0.1)
        assert pld.read_text() == "; bench copy\nGAL16V8\nGates\n"
        assert not app._unsaved()


async def test_save_as_writes_the_edits_to_the_new_name(app, tmp_path, monkeypatch):
    pld = tmp_path / "gates.pld"
    pld.write_text("GAL16V8\nGates\n")
    copy = tmp_path / "gates2.pld"
    monkeypatch.setattr(app, "push_screen", lambda screen, callback: callback(copy))
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _load(app, pld)
        await pilot.pause(0.3)
        app.query_one("#jed-view", TextArea).insert("; v2\n", (0, 0))
        await pilot.press("f12")
        await pilot.pause(0.5)
        assert copy.read_text() == "; v2\nGAL16V8\nGates\n"
        assert pld.read_text() == "GAL16V8\nGates\n"  # the original is untouched
        assert app._data_path == copy and not app._unsaved()


async def test_unsaved_edits_warn_once_before_they_are_lost(app, tmp_path):
    pld = tmp_path / "gates.pld"
    pld.write_text("GAL16V8\n")
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _load(app, pld)
        await pilot.pause(0.3)
        app.query_one("#jed-view", TextArea).insert("x", (0, 0))
        assert not app._may_discard("file", "f")  # first try only warns
        assert app._may_discard("file", "f")  # the second discards
        assert not app._may_discard("quit", "Ctrl+Q")  # another action warns afresh


async def test_jed_and_chp_stay_read_only(app):
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        for path in (JED, JED.parent / "gates_16v8.chp"):
            _load(app, path)
            await pilot.pause(0.5)
            assert app.query_one("#jed-view", TextArea).read_only
            assert app._saved_text is None


async def test_letters_type_in_the_editor_and_escape_leaves_it(app, tmp_path):
    pld = tmp_path / "gates.pld"
    pld.write_text("GAL16V8\n")
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _load(app, pld)
        await pilot.pause(0.3)
        view = app.query_one("#jed-view", TextArea)
        view.focus()
        await pilot.press("f")  # typed, not the File key
        assert view.text.startswith("f") and len(app.screen_stack) == 1
        await pilot.press("escape")
        assert app.focused is not view
        await pilot.press("f")  # now the File key: unsaved edit, so it only warns
        assert len(app.screen_stack) == 1 and app._discard_armed == "file"
        await pilot.press("f")  # pressed again: discards and opens the picker
        await pilot.pause(0.2)
        assert len(app.screen_stack) == 2


async def test_l_hides_and_shows_the_log_and_errors_bring_it_back(app, monkeypatch):
    saved: list[dict] = []
    monkeypatch.setattr(app_shell, "_save_state", lambda state: saved.append(dict(state)))
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        log = app.query_one(ActionLogPanel)
        tabs = app.query_one("#main-tabs", TabbedContent)
        tall = tabs.size.height
        await pilot.press("l")
        await pilot.pause(0.1)
        assert not log.display and saved[-1]["log_visible"] is False
        assert tabs.size.height > tall  # the tabs take the room
        app.log_action("[dim]a quiet line[/]")
        assert not log.display
        app.log_action("[red]WRITE  AT28C64 FAILED:[/]  no chip")
        await pilot.pause(0.1)
        assert log.display  # a failure is never hidden
        await pilot.press("l")
        assert not log.display
        await pilot.press("l")
        assert log.display and saved[-1]["log_visible"] is True


# --- .pld syntax colouring (MINIGECKO-01D, piece 3) --------------------------

def _named(lines, highlights, row):
    return {(lines[row].encode()[s:e].decode(), n) for s, e, n in highlights.get(row, [])}


def test_galasm_colours():
    from minigecko.ui.widgets.pld_text_area import galasm_highlights
    lines = (JED.parent / "counter4_16v8.pld").read_text().split("\n")
    h = galasm_highlights(lines)
    assert ("GAL16V8", "type.builtin") in _named(lines, h, 0)
    assert ("Counter4", "string") in _named(lines, h, 1)
    eq = next(i for i, ln in enumerate(lines) if ln.startswith("Q0.R"))
    assert {(".R", "method"), ("*", "keyword.operator"), ("; Q0 xor EN", "comment")} <= _named(lines, h, eq)
    desc = lines.index("DESCRIPTION")
    assert ("DESCRIPTION", "keyword") in _named(lines, h, desc)
    assert all(n == "comment" for _, n in _named(lines, h, desc + 2))  # free text after it


def test_cupl_colours_and_multiline_comments():
    from minigecko.ui.widgets.pld_text_area import cupl_highlights
    lines = ["Device g22v10 ;", "/* a comment", "   still comment */ X = A & !B ;", "Pin 3 = !MREQ ;"]
    h = cupl_highlights(lines)
    assert {("Device", "keyword"), ("g22v10", "type.builtin")} <= _named(lines, h, 0)
    assert _named(lines, h, 1) == {("/* a comment", "comment")}
    assert {("   still comment */", "comment"), ("&", "keyword.operator"), ("!", "keyword.operator")} <= _named(lines, h, 2)
    assert {("Pin", "keyword"), ("3", "number")} <= _named(lines, h, 3)


async def test_source_pane_is_coloured_and_other_text_is_not(app, tmp_path):
    from minigecko.ui.widgets.pld_text_area import PldTextArea
    notes = tmp_path / "notes.txt"
    notes.write_text("GAL16V8\nplain words\n")
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _load(app, JED.parent / "gates_16v8.pld")
        await pilot.pause(0.5)
        view = app.query_one("#jed-view", PldTextArea)
        assert view.pld and view._highlights[0]  # Textual still builds colours through our hook
        assert not view.soft_wrap  # equations keep their line
        view.insert("; new\n", (0, 0))
        await pilot.pause(0.1)
        assert view._highlights[0]  # rebuilt after an edit
        _load(app, notes)
        await pilot.pause(0.5)
        assert not view.pld and not any(view._highlights.values())
        assert view.soft_wrap  # prose still wraps
