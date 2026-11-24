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


def test_unknown_sources_are_refused_in_plain_words(tmp_path):
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
    broken = next(n for n, ln in enumerate(text.splitlines(), 1) if ln.startswith("AND  = A * Q"))
    result = compile_pld(src)
    assert not result.ok and result.line == broken and "unknown pinname" in result.message
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
        view = app.query_one("#jed-view", TextArea)
        view.cursor_location = (12, 3)
        await pilot.press("f9")
        await pilot.pause(2.0)
        assert (tmp_path / "gates_16v8.jed").exists()
        assert view.cursor_location == (12, 3)  # the editor was left alone
        assert "AND = A & B" in app.query_one("#jed-eqn", TextArea).text  # named from the .pld


# --- WinCUPL (CUPL sources) ------------------------------------------------

def _has_wincupl() -> bool:
    from minigecko.core.pld import wine_prefix
    exe = wine_prefix() / "drive_c" / "Wincupl" / "Shared" / "cupl.exe"
    return shutil.which("wine") is not None and exe.is_file()


needs_wincupl = pytest.mark.skipif(not _has_wincupl(), reason="Wine and WinCUPL are not installed")


def _cupl_copy(tmp_path: Path, name: str = "forbin80_mem") -> Path:
    src = tmp_path / f"{name}.pld"
    src.write_bytes((JED_DIR / "forbin80_mem.pld").read_bytes())
    return src


def test_missing_wincupl_names_the_path_it_checked(tmp_path, monkeypatch):
    from minigecko.core import pld
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/wine")
    pld.set_wine_prefix(str(tmp_path / "no-such-prefix"))
    try:
        result = compile_pld(_cupl_copy(tmp_path))
    finally:
        pld.set_wine_prefix("")
    assert not result.ok and "WinCUPL is not installed" in result.message
    assert "no-such-prefix" in result.message
    for word in ("apt", "pacman", "sudo"):
        assert word not in result.message


def test_missing_wine_is_named(tmp_path, monkeypatch):
    from minigecko.core.pld import WINE_MISSING
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert compile_pld(_cupl_copy(tmp_path)).message == WINE_MISSING


def test_non_ascii_is_refused_before_wincupl_runs(tmp_path, monkeypatch):
    src = _cupl_copy(tmp_path)
    src.write_text(src.read_text().replace("Revision 04", "Revision 04 — dash"))
    line = next(n for n, ln in enumerate(src.read_text().splitlines(), 1) if "—" in ln)
    monkeypatch.setattr("subprocess.run", lambda *a, **k: pytest.fail("WinCUPL must not run"))
    if not _has_wincupl():
        pytest.skip("the ASCII check runs after the WinCUPL install check")
    result = compile_pld(src)
    assert not result.ok and result.line == line and "ASCII" in result.message


@needs_wincupl
def test_wincupl_builds_the_committed_fuse_map_and_cleans_up(tmp_path):
    src = _cupl_copy(tmp_path)
    result = compile_pld(src)
    assert result.ok, result.message

    def fuses(path: Path) -> list[str]:
        return [ln for ln in path.read_text(errors="replace").splitlines() if ln.startswith("*L")]

    assert fuses(tmp_path / "forbin80_mem.jed") == fuses(JED_DIR / "forbin80_mem.jed")
    assert (tmp_path / "forbin80_mem.doc").exists()
    assert not [p for p in tmp_path.iterdir() if p.name.startswith("CB")]  # scratch removed


@needs_wincupl
def test_wincupl_syntax_error_names_its_line(tmp_path):
    src = _cupl_copy(tmp_path, "broken")
    lines = src.read_text().splitlines()
    n = next(i for i, ln in enumerate(lines) if ln.startswith("PAGE_CK"))
    lines[n] = "PAGE_CK = = PORT40 & WR"
    src.write_text("\n".join(lines) + "\n")
    result = compile_pld(src)
    assert not result.ok and result.line == n + 1 and "invalid syntax" in result.message


@needs_wincupl
def test_logged_wincupl_command_runs_unchanged_in_a_shell(tmp_path):
    import subprocess
    from minigecko.core import minipro

    src = _cupl_copy(tmp_path)
    heard: list[str] = []
    minipro.set_command_listener(lambda command, note: heard.append(command))
    try:
        assert compile_pld(src).ok
    finally:
        minipro.set_command_listener(None)
    (src.with_suffix(".jed")).unlink()
    (command,) = heard
    subprocess.run(["bash", "-c", command], capture_output=True, timeout=120, check=True)
    assert src.with_suffix(".jed").exists()  # the pasted command built it again


async def test_f9_waits_for_a_running_compile(app, tmp_path, monkeypatch):
    import time
    from minigecko.core import pld

    src = tmp_path / "gates.pld"
    src.write_text("GAL16V8\nGates\n")
    calls: list[float] = []

    def slow_compile(path):
        calls.append(time.time())
        time.sleep(0.6)
        return CompileResult(False, "line 1: nope", 1)

    monkeypatch.setattr(pld, "compile_pld", slow_compile)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        _open(app, src)
        await pilot.pause(0.3)
        await pilot.press("f9")
        await pilot.pause(0.1)
        assert app._compiling and app.check_action("compile", ()) is None  # greyed out
        await pilot.press("f9")  # ignored while the first runs
        await pilot.pause(1.0)
        assert len(calls) == 1 and not app._compiling
        await pilot.press("f9")  # free again afterwards
        await pilot.pause(1.0)
        assert len(calls) == 2


# --- Compiler options (MINIGECKO-01B) --------------------------------------

@pytest.fixture
def default_options():
    from minigecko.core import pld
    pld.set_compiler_options({})
    yield pld
    pld.set_compiler_options({})


def test_default_options_write_jed_doc_and_jed_chp(default_options):
    pld = default_options
    assert pld.galette_flags() == ["-f", "-p"]  # no .fus, no .pin, no security fuse
    assert pld.galette_outputs() == [".jed", ".chp"]
    assert pld.wincupl_flags() == ["-j", "-n", "-x", "-f", "-m1"]
    assert pld.wincupl_outputs() == [".jed", ".doc"]


def test_each_option_changes_its_flag(default_options):
    pld = default_options
    pld.set_compiler_options({"galette": {"chp": False, "pin": True, "secure": True}})
    assert pld.galette_flags() == ["-c", "-f", "-s"]
    assert pld.galette_outputs() == [".jed", ".pin"]
    pld.set_compiler_options({"wincupl": {"simulator": True, "macros": True, "minimize": 3}})
    assert pld.wincupl_flags() == ["-j", "-n", "-a", "-x", "-f", "-e", "-m3"]
    assert pld.wincupl_outputs() == [".jed", ".doc", ".abs", ".sim", ".mx"]
    pld.set_compiler_options({"wincupl": {"doc_equations": False, "doc_fuse_plot": False}})
    assert pld.wincupl_outputs() == [".jed"]  # neither -x nor -f: no .doc


@needs_wincupl
def test_wincupl_writes_only_what_the_options_ask_for(tmp_path, default_options):
    src = _cupl_copy(tmp_path)
    result = compile_pld(src)
    assert result.ok and result.message == "wrote forbin80_mem.jed and forbin80_mem.doc"
    assert sorted(p.suffix for p in tmp_path.iterdir()) == [".doc", ".jed", ".pld"]


async def test_options_screen_saves_to_state(app, monkeypatch, default_options):
    from textual.widgets import Checkbox, Select
    saved: list[dict] = []
    monkeypatch.setattr(app_shell, "_save_state", lambda state: saved.append(dict(state)))
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause(0.5)
        await pilot.press("o")
        await pilot.pause(0.3)
        screen = app.screen
        screen.query_one("#opt-wincupl-simulator", Checkbox).value = True
        screen.query_one("#opt-wincupl-minimize", Select).value = 4
        await pilot.pause(0.2)  # let the layout settle before clicking
        await pilot.click("#opt-save")
        await pilot.pause(0.3)
        assert len(app.screen_stack) == 1
    assert saved[-1]["compiler_options"]["wincupl"]["simulator"] is True
    assert saved[-1]["compiler_options"]["wincupl"]["minimize"] == 4
    assert default_options.wincupl_flags() == ["-j", "-n", "-a", "-x", "-f", "-m4"]


async def test_options_buttons_stay_on_a_short_terminal(app):
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.5)
        await pilot.press("o")
        await pilot.pause(0.5)
        save = app.screen.query_one("#opt-save")
        assert save.region.bottom <= 30 and save.region.height == 3  # fully on screen
        scroll = app.screen.query_one("VerticalScroll")
        assert scroll.max_scroll_y > 0  # the options scroll instead of being cut off
