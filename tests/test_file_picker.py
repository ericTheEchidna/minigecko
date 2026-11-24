"""Save mode of the file picker: name a new file, ask before overwriting."""

from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.widgets import DirectoryTree, Input

from minigecko.ui.modals.file_picker import FilePickerScreen


class _Harness(App):
    def __init__(self, start: Path, save_name: str | None) -> None:
        super().__init__()
        self._start, self._save_name = start, save_name
        self.result: Path | None | str = "not dismissed"

    def on_mount(self) -> None:
        def _done(path: Path | None) -> None:
            self.result = path

        self.push_screen(FilePickerScreen(self._start, save_name=self._save_name), _done)


async def test_save_to_a_new_file(tmp_path: Path) -> None:
    app = _Harness(tmp_path, "AT28C64.bin")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.query_one("#save-name", Input).value == "AT28C64.bin"
        await pilot.press("enter")
        await pilot.pause()
    assert app.result == tmp_path / "AT28C64.bin"


async def test_existing_file_needs_a_second_enter(tmp_path: Path) -> None:
    (tmp_path / "dump.bin").write_bytes(b"\x00")
    app = _Harness(tmp_path, "dump.bin")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.result == "not dismissed"
        await pilot.press("enter")
        await pilot.pause()
    assert app.result == tmp_path / "dump.bin"


async def test_enter_in_tree_picks_folder_without_saving(tmp_path: Path) -> None:
    (tmp_path / "roms").mkdir()
    app = _Harness(tmp_path, "AT28C64.bin")
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one("#filetree", DirectoryTree)
        tree.focus()
        await pilot.pause(0.3)  # let the tree load its first level
        tree.move_cursor_to_line(1)  # line 0 is the root, line 1 is roms/
        await pilot.press("enter")
        await pilot.pause()
        assert app.result == "not dismissed"
        assert app.screen.query_one("#save-name", Input).has_focus
        await pilot.press("enter")
        await pilot.pause()
    assert app.result == tmp_path / "roms" / "AT28C64.bin"


async def test_open_mode_has_no_name_box(tmp_path: Path) -> None:
    app = _Harness(tmp_path, None)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.screen.query("#save-name")


async def test_open_mode_enter_on_tree_cursor_opens_file(tmp_path: Path) -> None:
    (tmp_path / "rom.bin").write_bytes(b"\x00")
    app = _Harness(tmp_path, None)
    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        app.screen.query_one("#filetree", DirectoryTree).move_cursor_to_line(1)
        await pilot.press("enter")
        await pilot.pause()
    assert app.result == tmp_path / "rom.bin"
