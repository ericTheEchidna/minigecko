"""Compiling a .pld: the language picks the tool; Galette errors point at a line."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from minigecko.core import emulator, minipro
from minigecko.core.pld import (
    CUPL, GALASM, GALETTE_MISSING, CompileResult, compile_pld, pld_language,
)
from minigecko.ui import app_shell
from minigecko.ui.app_shell import MinigeckoApp
from minigecko.ui.state import _DEFAULT_STATE

JED_DIR = Path(__file__).parent / "data" / "jed"
needs_galette = pytest.mark.skipif(shutil.which("galette") is None, reason="Galette is not installed")


def test_language_comes_from_the_text():
    assert pld_language((JED_DIR / "gates_16v8.pld").read_text()) == GALASM
    assert pld_language((JED_DIR / "counter4_16v8.pld").read_text()) == GALASM
    assert pld_language((JED_DIR / "forbin80_mem.pld").read_text()) == CUPL
    assert pld_language("; a comment first\nGAL22V10\nSig\n") == GALASM
    assert pld_language("hello\nworld\n") is None


def test_missing_galette_is_named_without_an_install_command(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    src = tmp_path / "gates.pld"
    src.write_bytes((JED_DIR / "gates_16v8.pld").read_bytes())
    result = compile_pld(src)
    assert not result.ok and result.message == GALETTE_MISSING
    for word in ("apt", "pacman", "cargo install", "sudo"):
        assert word not in result.message


def test_cupl_and_unknown_sources_are_refused_in_plain_words(tmp_path):
    result = compile_pld(JED_DIR / "forbin80_mem.pld")
    assert not result.ok and "WinCUPL" in result.message
    junk = tmp_path / "junk.pld"
    junk.write_text("hello\n")
    result = compile_pld(junk)
    assert not result.ok and "Not a GALasm or CUPL source" in result.message


@needs_galette
def test_galette_builds_the_same_fuse_map_as_the_committed_jed(tmp_path):
    src = tmp_path / "gates_16v8.pld"
    src.write_bytes((JED_DIR / "gates_16v8.pld").read_bytes())
    result = compile_pld(src)
    assert result.ok, result.message
    assert (tmp_path / "gates_16v8.jed").read_bytes() == (JED_DIR / "gates_16v8.jed").read_bytes()
    assert (tmp_path / "gates_16v8.chp").exists()
    assert not (tmp_path / "gates_16v8.fus").exists() and not (tmp_path / "gates_16v8.pin").exists()


@needs_galette
def test_a_galette_error_names_its_line(tmp_path):
    src = tmp_path / "broken.pld"
    text = (JED_DIR / "gates_16v8.pld").read_text().replace("AND  = A * B", "AND  = A * Q")
    src.write_text(text)
    result = compile_pld(src)
    assert not result.ok and result.line == 7 and "unknown pinname" in result.message
    assert not (tmp_path / "broken.jed").exists()


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(minipro, "_transport", emulator.emulate)
    monkeypatch.setattr(app_shell, "_save_state", lambda state: None)
    monkeypatch.setattr(app_shell, "_load_state", lambda: dict(_DEFAULT_STATE))
    return MinigeckoApp()


def _open(app: MinigeckoApp, path: Path) -> None:
    app._file_label, app._data_path, app._read_from = str(path), path, None
    app.refresh_bindings()
    app._load_hex(path)


async def test_f9_saves_then_compiles_and_an_error_moves_the_cursor(app, tmp_path, monkeypatch):
    from textual.widgets import TextArea
    from minigecko.core import pld

    src = tmp_path / "gates.pld"
    src.write_text("GAL16V8\nGates\n")
    seen: list[str] = []

    def fake_compile(path):
        seen.append(path.read_text())  # what was on disk when the compile ran
        return CompileResult(False, "line 2: unknown pinname", 2)

    monkeypatch.setattr(pld, "compile_pld", fake_compile)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _open(app, src)
        await pilot.pause(0.3)
        view = app.query_one("#jed-view", TextArea)
        view.insert("; edited\n", (0, 0))
        await pilot.press("f9")
        await pilot.pause(0.5)
        assert seen == ["; edited\nGAL16V8\nGates\n"]  # saved before compiling
        assert view.cursor_location == (1, 0)  # line 2, counted from 1
        assert app.focused is view


@needs_galette
@pytest.mark.skipif(shutil.which("jedutil") is None, reason="MAME jedutil is not installed")
async def test_f9_compile_reloads_the_equations(app, tmp_path):
    from textual.widgets import TextArea

    src = tmp_path / "gates_16v8.pld"
    src.write_bytes((JED_DIR / "gates_16v8.pld").read_bytes())
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _open(app, src)
        await pilot.pause(0.5)
        assert "No gates_16v8.jed" in app.query_one("#jed-eqn", TextArea).text
        await pilot.press("f9")
        await pilot.pause(2.0)
        assert (tmp_path / "gates_16v8.jed").exists()
        assert "o12 = i2 & i3" in app.query_one("#jed-eqn", TextArea).text
