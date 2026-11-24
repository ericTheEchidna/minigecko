"""Every minipro run is logged as a terminal command; every minipro option has help."""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from minigecko.core import emulator, minipro
from minigecko.ui import app_shell
from minigecko.ui.app_shell import MinigeckoApp
from minigecko.ui.panels import ActionLogPanel

OPTIONS_PAGE = (
    Path(__file__).parent.parent / "minigecko" / "data" / "help" / "18-minipro-options.md"
)


@pytest.fixture
def heard(monkeypatch):
    """Commands the listener receives, and the args the emulator really ran."""
    commands: list[str] = []
    ran: list[list[str]] = []

    def transport(args, input_data, progress_cb):
        ran.append(list(args))
        return emulator.emulate(args, input_data, progress_cb)

    monkeypatch.setattr(minipro, "_transport", transport)
    monkeypatch.setattr(minipro, "_override_binary", None)
    minipro.set_command_listener(commands.append)
    yield commands, ran
    minipro.set_command_listener(None)


def test_each_operation_logs_the_command_it_runs(heard, tmp_path):
    commands, ran = heard
    out = tmp_path / "my roms" / "read (1).bin"  # spaces and brackets must survive
    out.parent.mkdir()
    minipro.read_device("AT28C64", out)
    minipro.checked_blank_check("AT28C64")
    minipro.erase_device("AT28C64")
    minipro.logic_test("7400")

    assert len(commands) == len(ran) == 5  # blank check is a pin check, then -b
    for command, args in zip(commands, ran):
        words = shlex.split(command)
        assert words[0] == "minipro"
        assert words[1:] == args  # pastes into a shell as the very same argv
    assert str(out) in shlex.split(commands[0])


def test_command_names_the_configured_binary(monkeypatch):
    monkeypatch.setattr(minipro, "_override_binary", "/opt/mini pro/minipro")
    assert minipro.command_line(["-p", "AT28C64", "-b"]) == (
        "'/opt/mini pro/minipro' -p AT28C64 -b"
    )


def test_a_refused_jed_runs_and_logs_nothing(heard, tmp_path):
    commands, ran = heard
    bad = Path(__file__).parent / "data" / "jed" / "bad_checksum_22v10.jed"
    result = minipro.write_device("ATF16V8B", bad)
    assert not result.ok and result.data.get("refused")
    assert commands == [] and ran == []


async def test_log_shows_commands_and_y_copies_the_last(monkeypatch):
    monkeypatch.setattr(minipro, "_transport", emulator.emulate)
    monkeypatch.setattr(app_shell, "_save_state", lambda state: None)
    monkeypatch.setattr(app_shell.shutil, "which", lambda name: None)  # no real xclip
    app = MinigeckoApp()
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(0.5)
        app._do_pin_check("AT28C64")
        await pilot.pause(1.0)
        await pilot.press("y")
        messages = app.query_one(ActionLogPanel)._messages
        assert any("$ minipro -p AT28C64 -z" in m for m in messages)
        assert app.clipboard == "minipro -p AT28C64 -z"
    assert minipro._command_listener is None  # the app drops its listener on exit


def _man_page_options() -> set[str]:
    """Every -x and --long option the installed minipro's manual page names."""
    if shutil.which("minipro") is None or shutil.which("man") is None:
        pytest.skip("minipro is not installed")
    found = subprocess.run(["man", "-w", "minipro"], capture_output=True, text=True)
    if found.returncode != 0:
        pytest.skip("minipro's manual page is not installed")
    text = Path(found.stdout.strip()).read_text(errors="replace")
    options: set[str] = set()
    for line in text.splitlines():
        if not line.startswith(".B "):
            continue
        options |= {f"--{m}" for m in re.findall(r"\\-\\-([a-z_]+)", line)}
        options |= {f"-{m}" for m in re.findall(r"(?<!-)\\-([A-Za-z])(?![A-Za-z_])", line)}
    return options


def test_options_page_covers_every_installed_minipro_option():
    options = _man_page_options()
    assert len(options) > 60, "the manual page parse found too few options"
    page = OPTIONS_PAGE.read_text()
    documented = set(re.findall(r"`(--?[A-Za-z_]+)", page))
    missing = sorted(options - documented)
    assert not missing, f"minipro options missing from {OPTIONS_PAGE.name}: {missing}"


def test_options_page_is_in_the_contents():
    toc = OPTIONS_PAGE.with_name("toc.md").read_text()
    assert f"({OPTIONS_PAGE.name})" in toc
