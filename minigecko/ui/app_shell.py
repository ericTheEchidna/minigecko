"""Main Textual application shell for MiniGecko."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import textwrap
import threading
from pathlib import Path
from typing import ClassVar

from rich.markup import escape
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane, TextArea

from minigecko import __version__
from minigecko.ui.hexdump import _MAX_BYTES
from minigecko.ui.modals import ChipSelectScreen, FilePickerScreen, HelpScreen, ICOpsScreen, infer_chip_type
from minigecko.ui.modals.help_screen import is_manual_cached, load_manual_text
from minigecko.ui.panels import ActionLogPanel, HexPanel, ICInfoPanel
from minigecko.ui.state import _load_state, _save_state
from minigecko.ui.widgets import HResizeHandle, VResizeHandle

logger = logging.getLogger(__name__)

# Control bytes a text file may hold: tab, LF, FF, CR, and JEDEC's STX/ETX.
_TEXT_CONTROLS = {0x09, 0x0A, 0x0C, 0x0D, 0x02, 0x03}


def _as_text(data: bytes) -> str | None:
    """*data* as text when it reads as UTF-8 with no stray control bytes, else None.

    A ROM image fails this: it holds zero bytes, other control bytes, or 0xFF
    runs that are not UTF-8. An empty file is not text (it shows as empty hex).
    """
    if not data or any(b < 0x20 and b not in _TEXT_CONTROLS for b in data[:65536]):
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


class MinigeckoApp(App):
    """MiniGecko open source programmer suite."""

    TITLE = f"minigecko v{__version__}"

    DEFAULT_CSS = """
    #main-tabs { height: 1fr; }
    #main-tabs TabPane { padding: 0; }
    #data-empty { padding: 1 2; color: $text-muted; }
    #jed-pair { height: 1fr; }
    #jed-pair > Vertical { width: 1fr; height: 1fr; }
    #jed-pair .pane-title { background: $panel; color: $text-muted; padding: 0 1; height: 1; }
    #jed-pair #eqn-title { height: auto; }  /* the decompile note may wrap */
    #jed-view, #jed-eqn { height: 1fr; border: none; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("f", "file", "File"),
        Binding("ctrl+s", "save", "Save"),
        Binding("f12", "save_as", "Save as"),
        Binding("f9", "compile", "Compile"),
        Binding("escape", "leave_editor", "Leave editor", show=False),
        Binding("s", "select_ic", "Select IC"),
        Binding("d", "ic_ops", "IC Ops"),
        Binding("h", "help", "Help"),
        Binding("y", "copy_command", "Copy command"),
        Binding("1","show_tab('tab-chip')", "Chip", show=False),
        Binding("2", "show_tab('tab-data')", "Data", show=False),
        Binding("ctrl+d", "toggle_dark", "Theme", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._state = _load_state()
        self._programmer_label = "detecting…"
        self._file_label: str | None = None
        self._data_path: Path | None = None
        self._read_from: str | None = None  # chip the loaded data was read from
        self._selected_ic: str | None = None
        self._last_command: str | None = None  # last external command line run
        self._saved_text: str | None = None  # editable text as last saved; None = not editable
        self._discard_armed: str | None = None  # action that may discard edits on its next press
        self._compiling = False  # a compile is running; F9 waits for it

    def _on_command(self, command: str, note: str = "") -> None:
        """Log an external command line; called from any thread before it runs."""
        if threading.current_thread() is threading.main_thread():
            self._log_command(command, note)
        else:
            self.call_from_thread(self._log_command, command, note)

    def _log_command(self, command: str, note: str = "") -> None:
        self._last_command = command
        self.log_action(f"[dim]$ {escape(command)}[/]")
        if note:
            self.log_action(f"[yellow]  note:[/] {escape(note)}")

    def action_copy_command(self) -> None:
        """Copy the last command line (minipro or jedutil), ready for a terminal."""
        if not self._last_command:
            self.notify("No command has run yet.")
            return
        self.copy_to_clipboard(self._last_command)  # OSC 52, for terminals that support it
        xclip = shutil.which("xclip")
        if xclip:  # X11 clipboard for terminals that ignore OSC 52
            try:
                subprocess.run(
                    [xclip, "-selection", "clipboard"],
                    input=self._last_command.encode(), timeout=2, check=False,
                    # xclip stays behind to own the selection: keep it off our streams
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                logger.debug("xclip failed: %s", exc)
        self.notify(f"Copied: {self._last_command}", markup=False)

    def log_action(self, message: str) -> None:
        """Write a timestamped entry to the action log from the main thread."""
        try:
            self.query_one(ActionLogPanel).log(message)
        except Exception as exc:
            logger.debug("Action log unavailable during write: %s", exc)

    def _log(self, message: str) -> None:
        """Thread-safe log wrapper for worker methods."""
        self.call_from_thread(self.log_action, message)

    def _make_progress_cb(self):
        """Return a progress callback that updates the action log progress bar."""
        panel = self.query_one(ActionLogPanel)

        def _cb(percent: int | None, label: str) -> None:
            self.call_from_thread(panel.show_progress, percent)

        return _cb

    def _hide_progress(self) -> None:
        self.query_one(ActionLogPanel).hide_progress()

    def _update_subtitle(self) -> None:
        parts = [self._programmer_label]
        if self._file_label:
            parts.append(self._file_label)
        self.sub_title = "  │  ".join(parts)

    def get_last_directory(self) -> Path:
        """Return the last file-browser directory with a safe fallback."""
        last = Path(self._state.get("last_directory", str(Path.home())))
        return last if last.is_dir() else Path.home()

    def get_write_source_label(self) -> str:
        """Return a short label describing the current write source."""
        if self._file_label:
            return Path(self._file_label).name
        if self._data_path:
            return f"read from {self._read_from}" if self._read_from else "device read"
        return "(no file loaded)"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        # Chip work and data work are separate tabs; the log sits under both.
        with TabbedContent(id="main-tabs"):
            with TabPane("1 Chip", id="tab-chip"):
                yield ICInfoPanel()
            with TabPane("2 Data", id="tab-data"):
                yield Static(
                    "No data loaded. Press f to open a file, or read a chip from IC Ops (d).",
                    id="data-empty",
                )
                hex_panel = HexPanel()
                hex_panel.display = False
                yield hex_panel
                # A .jed shows its raw fuse map beside the decompiled equations.
                with Horizontal(id="jed-pair") as pair:
                    pair.display = False
                    with Vertical(id="jed-left"):
                        yield Static("Fuse map (.jed)", id="jed-title", classes="pane-title")
                        yield TextArea("", read_only=True, id="jed-view")
                    yield HResizeHandle("jed-left", id="jed-split")
                    with Vertical(id="jed-right"):
                        yield Static("Equations", id="eqn-title", classes="pane-title")
                        yield TextArea("", read_only=True, id="jed-eqn")
        yield VResizeHandle()
        yield ActionLogPanel()
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(ActionLogPanel).styles.height = self._state["log_height"]
        self.query_one("#jed-left").styles.width = f"{self._state['jed_split']}%"
        from minigecko.core import set_binary_path, set_command_listener

        set_binary_path(self._state.get("minipro_path", ""))
        from minigecko.core.pld import set_wine_prefix

        set_wine_prefix(self._state.get("wincupl_prefix", ""))
        set_command_listener(self._on_command)
        self._poll_programmer()
        self._preload_device_db()
        self._preload_help_manual()

    def on_unmount(self) -> None:
        from minigecko.core import set_command_listener

        set_command_listener(None)  # the listener is module-wide; drop this app's

    @work(thread=True)
    def _poll_programmer(self) -> None:
        from minigecko.core import detect_programmer, is_emulated

        emulated = is_emulated()
        info = detect_programmer()
        if info.connected:
            from minigecko.core.device_db import use_programmer

            use_programmer(info.hardware)
            hw = info.hardware or "TL866II+"
            fw = info.firmware
            if emulated:
                label = f"Programmer: {hw}  fw {fw}  [EMULATED]"
            else:
                label = f"Programmer: {hw}  fw {fw}"
        else:
            label = "Programmer: not detected"

        def _update() -> None:
            self._programmer_label = label
            self._update_subtitle()
            if info.connected:
                if emulated:
                    self.log_action(f"[yellow]PROGRAMMER  emulated[/]  {info.hardware}  fw {info.firmware}")
                else:
                    self.log_action(f"[green]PROGRAMMER  connected[/]  {info.hardware}  fw {info.firmware}")
            else:
                self.log_action("[yellow]PROGRAMMER  not detected[/]")

        self.call_from_thread(_update)

    @work(thread=True)
    def _preload_device_db(self) -> None:
        from minigecko.core import get_db

        self._log("[dim]Loading device database…[/]")
        db = get_db()
        self._log(f"[dim]{len(db):,} devices ready.[/]")

    @work(thread=True)
    def _preload_help_manual(self) -> None:
        load_manual_text()

    def _unsaved(self) -> bool:
        """True when the open text has edits not yet saved."""
        if self._saved_text is None:
            return False
        return self.query_one("#jed-view", TextArea).text != self._saved_text

    def _may_discard(self, action: str, again: str) -> bool:
        """True when *action* may replace the open text.

        With unsaved edits the first try only warns; trying *action* again
        discards them.
        """
        if not self._unsaved() or self._discard_armed == action:
            self._discard_armed = None
            return True
        self._discard_armed = action
        name = self._data_path.name if self._data_path else "the open file"
        self.notify(
            f"{name} has unsaved changes. Press Ctrl+S to save them, "
            f"or {again} again to discard them.",
            severity="warning",
        )
        return False

    def action_leave_editor(self) -> None:
        """Escape leaves a text pane, so letter keys reach the app again."""
        if isinstance(self.focused, TextArea):
            self.set_focus(None)

    async def action_quit(self) -> None:
        if self._may_discard("quit", "Ctrl+Q"):
            self.exit()

    def action_file(self) -> None:
        if not self._may_discard("file", "f"):
            return
        start = self.get_last_directory()

        def _on_file(path: Path | None) -> None:
            if path:
                self._state["last_directory"] = str(path.parent)
                _save_state(self._state)
                self._file_label = str(path)
                self._data_path = path
                self._read_from = None
                self.refresh_bindings()
                self._update_subtitle()
                self.log_action(f"[green]FILE  opened[/]  {path.name}  ({path.stat().st_size:,} B)")
                self._load_hex(path)

        self.push_screen(FilePickerScreen(start_path=start), _on_file)

    def action_show_tab(self, tab_id: str) -> None:
        self.query_one("#main-tabs", TabbedContent).active = tab_id

    @work(thread=True)
    def _load_hex(self, path: Path) -> None:
        """Show *path* in the Data tab: a .jed, .pld or .chp as text beside
        equations, other plain text on its own, anything else as hex."""
        panel = self.query_one(HexPanel)
        self.call_from_thread(panel.clear)

        try:
            data = path.read_bytes()
        except OSError as exc:
            self._log(f"[red]FILE  read error:[/]  {exc}")
            return

        if path.suffix.lower() == ".jed":
            from minigecko.core.jedec import decompile

            text = data.decode("ascii", errors="replace").replace("\x02", "").replace("\x03", "")
            equations, note = decompile(path, self._selected_ic or "")
            self.call_from_thread(self._show_data, None, text, equations, note)
            return

        beside_jed = {".pld": "Source", ".chp": "Pinout"}  # shown beside the .jed's equations
        kind = beside_jed.get(path.suffix.lower())
        if kind is not None:
            text = data.decode("utf-8", errors="replace")
            if kind == "Pinout":  # Galette centres its drawing on a wide page
                text = textwrap.indent(textwrap.dedent(text).strip("\n"), "  ") + "\n"
            equations, note = self._equations_beside(path)
            self.call_from_thread(
                lambda: self._show_data(
                    None, text, equations, note, f"{kind} ({path.name})",
                    editable=kind == "Source",  # a .chp is Galette's output: read-only
                )
            )
            return

        truncated = len(data) > _MAX_BYTES
        if truncated:
            data = data[:_MAX_BYTES]
            self._log(f"[yellow]FILE  truncated — showing first {_MAX_BYTES // 2**20} MB[/]")

        text = _as_text(data)
        if text is not None:  # plain text reads as text, across the whole tab
            self.call_from_thread(
                lambda: self._show_data(None, text, None, "", path.name, solo=True, editable=True)
            )
            return

        self.call_from_thread(self._show_data, data, None)

    def _show_data(
        self,
        data: bytes | None,
        text: str | None,
        equations: str | None = None,
        note: str = "",
        text_title: str = "Fuse map (.jed)",
        solo: bool = False,
        editable: bool = False,
    ) -> None:
        """Fill the Data tab and switch to it: hex for *data*, or *text*
        (titled *text_title*) beside the decompiled *equations*, or *note*
        saying why not. With *solo*, the text fills the tab on its own; with
        *editable*, it can be changed and saved."""
        self._saved_text = text if (text is not None and editable) else None
        self._discard_armed = None
        self.query_one("#data-empty").display = False
        hex_panel = self.query_one(HexPanel)
        hex_panel.display = data is not None
        self.query_one("#jed-pair").display = text is not None
        if data is not None:
            hex_panel.load(data)
        if text is not None:
            self.query_one("#jed-right").display = not solo
            self.query_one("#jed-split").display = not solo
            self.query_one("#jed-left").styles.width = (
                "1fr" if solo else f"{self._state['jed_split']}%"
            )
            self.query_one("#jed-title", Static).update(
                f"{text_title}: editable, Ctrl+S saves" if editable else text_title
            )
            view = self.query_one("#jed-view", TextArea)
            view.read_only = not editable
            view.show_line_numbers = editable  # compiler errors name a line
            view.load_text(text)
        if text is not None and not solo:
            self._set_equations(equations, note)
        self.action_show_tab("tab-data")

    def _set_equations(self, equations: str | None, note: str) -> None:
        """Fill the Equations pane; the note goes in its title, so the pane
        holds only jedutil's output (or, without equations, why not)."""
        title = self.query_one("#eqn-title", Static)
        if equations is not None:
            title.update(f"Equations: {note}" if note else "Equations")
            self.query_one("#jed-eqn", TextArea).load_text(equations)
        else:
            title.update("Equations: not available")
            self.query_one("#jed-eqn", TextArea).load_text(note)

    def _equations_beside(self, path: Path) -> tuple[str | None, str]:
        """Equations of the .jed named like *path* (a .pld or .chp), and a note."""
        from minigecko.core.jedec import decompile

        jed = next(
            (p for p in (path.with_suffix(".jed"), path.with_suffix(".JED")) if p.exists()),
            None,
        )
        if jed is None:
            return None, (
                f"No {path.stem}.jed beside {path.name}. Compile the .pld with F9, "
                "then the equations show here."
            )
        equations, note = decompile(jed, self._selected_ic or "")
        return equations, f"From {jed.name}. {note}"

    def save_jed_split(self, percent: float) -> None:
        """Remember the Data tab's fuse map share of the width, in percent."""
        self._state["jed_split"] = percent
        _save_state(self._state)

    def save_log_height(self) -> None:
        panel = self.query_one(ActionLogPanel)
        self._state["log_height"] = int(panel.styles.height.value)  # type: ignore[union-attr]
        _save_state(self._state)

    def _set_selected_ic(self, chip: str) -> None:
        self._selected_ic = chip
        self.refresh_bindings()  # shows the IC Ops key in the footer
        self.query_one(ICInfoPanel).show(chip)
        self.action_show_tab("tab-chip")
        self.log_action(f"[green]IC  selected[/]  {chip}")

    def _open_chip_select(self) -> None:
        def _on_selected(chip: str | None) -> None:
            if chip:
                self._set_selected_ic(chip)

        self.push_screen(ChipSelectScreen(), _on_selected)

    def action_select_ic(self) -> None:
        self._open_chip_select()

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == "ic_ops":
            return bool(self._selected_ic)
        if action in ("save", "save_as"):
            return bool(self._data_path)
        if action == "compile":
            if not self._data_path or self._data_path.suffix.lower() != ".pld" or self._read_from:
                return False
            return None if self._compiling else True  # None: shown, greyed out, while it runs
        return True

    def action_ic_ops(self) -> None:
        if not self._selected_ic:
            return
        from minigecko.core import get_device

        entry = get_device(self._selected_ic)
        if entry:
            chip_type = entry.get("type", 1)
            is_isp = entry.get("is_isp", False)
            can_erase = entry.get("can_erase", True)
        else:
            chip_type = infer_chip_type(self._selected_ic)
            is_isp = False
            can_erase = True
        self.push_screen(ICOpsScreen(self._selected_ic, chip_type=chip_type, is_isp=is_isp, can_erase=can_erase))

    def run_logic_test_op(self, ic_name: str) -> None:
        self._do_logic_test(ic_name)

    @work(thread=True)
    def _do_logic_test(self, ic_name: str) -> None:
        from minigecko.core import logic_test

        self._log(f"[cyan]RAM/LOGIC TEST[/]  {ic_name} …")
        result = logic_test(ic_name)
        errors = result.data.get("errors", 0)
        summary = result.data.get("summary", "")
        failed = (not result.ok) or errors > 0 or "failed" in summary.lower()
        if failed:
            self._log(f"[red]RAM/LOGIC TEST  {ic_name} FAIL[/]  {summary or result.stderr.strip()}")
            pin_table = result.data.get("detail", "")
            if pin_table:
                for line in pin_table.splitlines():
                    self._log(f"[dim]{line}[/]")
        else:
            self._log(f"[green]RAM/LOGIC TEST  {ic_name} OK[/]  {summary or 'all cells passed'}")

    def run_pin_check_op(self, ic_name: str) -> None:
        self._do_pin_check(ic_name)

    @work(thread=True)
    def _do_pin_check(self, ic_name: str) -> None:
        from minigecko.core import pin_check_device

        self._log(f"[cyan]PIN CHECK[/]  {ic_name} …")
        result = pin_check_device(ic_name)
        if result.ok:
            self._log(f"[green]PIN CHECK  {ic_name} OK[/]  all pins contact")
        else:
            self._log(f"[red]PIN CHECK  {ic_name} FAIL:[/]  {result.output.strip()}")

    def run_read_op(self, ic_name: str) -> None:
        if not self._may_discard("read", "Read"):  # the read replaces the Data tab
            return
        self._do_read(ic_name)

    @work(thread=True)
    def _do_read(self, ic_name: str) -> None:
        import tempfile
        from minigecko.core import read_device
        from minigecko.core.minipro import format_for_device

        suffix = ".jed" if format_for_device(ic_name) == "JED" else ".bin"
        fd, tmp_str = tempfile.mkstemp(prefix=f"minigecko_{ic_name}_", suffix=suffix)
        os.close(fd)
        tmp = Path(tmp_str)
        self._log(f"[cyan]READ[/]  {ic_name} …")
        result = read_device(ic_name, tmp, progress_cb=self._make_progress_cb())
        self.call_from_thread(self._hide_progress)
        if result.ok:
            if "chip id mismatch" in result.output.lower():
                self._log(f"[yellow]READ  {ic_name} chip ID mismatch — read anyway[/]")
            self.call_from_thread(self._on_read_done, ic_name, tmp)
        else:
            tmp.unlink(missing_ok=True)
            self._log(f"[red]READ  {ic_name} FAILED:[/]  {result.output}")

    def _on_read_done(self, ic_name: str, path: Path) -> None:
        size = path.stat().st_size
        self.log_action(f"[green]READ  {ic_name} OK[/]  {size:,} B  (Ctrl+S to save it)")
        self._data_path = path
        self._read_from = ic_name
        self._file_label = None  # the loaded data is the chip read now, not the last file
        self._update_subtitle()
        self.refresh_bindings()
        self._load_hex(path)

    def action_save(self) -> None:
        """Save edits to the open file in place; a chip read has no file yet,
        so it goes to Save as."""
        if not self._data_path:
            self.log_action("[yellow]SAVE  no data loaded[/]")
            return
        if self._read_from:
            self.action_save_as()
            return
        if not self._unsaved():
            self.notify("No changes to save.")
            return
        self._write_edits()

    def _write_edits(self) -> bool:
        """Write the open text to its file; False (and logged) on failure."""
        text = self.query_one("#jed-view", TextArea).text
        try:
            self._data_path.write_text(text)
        except OSError as exc:
            self.log_action(f"[red]SAVE  failed:[/]  {exc}")
            return False
        self._saved_text = text
        self._discard_armed = None
        self.log_action(f"[green]SAVE  OK[/]  {self._data_path}")
        return True

    def action_compile(self) -> None:
        """Save the open .pld if edited, then compile it beside itself."""
        path = self._data_path
        if not path or path.suffix.lower() != ".pld" or self._read_from:
            return
        if self._compiling:  # one compile at a time: results must not cross
            self.notify(f"Compiling {path.name}…")
            return
        if self._unsaved() and not self._write_edits():
            return
        self._compiling = True
        self.refresh_bindings()
        self._do_compile(path)

    @work(thread=True)
    def _do_compile(self, path: Path) -> None:
        from minigecko.core.pld import compile_pld

        self._log(f"[cyan]COMPILE[/]  {path.name} …")
        try:
            result = compile_pld(path)
        finally:
            self.call_from_thread(self._compile_done)
        if result.ok:
            self._log(f"[green]COMPILE  {path.name} OK[/]  {result.message}")
            # Only the equations change; the editor keeps its cursor and scroll.
            equations, note = self._equations_beside(path)
            self.call_from_thread(self._set_equations, equations, note)
            return
        self._log(f"[red]COMPILE  {path.name} FAILED:[/]  {escape(result.message)}")
        if result.line:
            self.call_from_thread(self._show_error_line, result.line)

    def _compile_done(self) -> None:
        self._compiling = False
        self.refresh_bindings()

    def _show_error_line(self, line: int) -> None:
        """Put the cursor on *line* (1-based) of the open source."""
        view = self.query_one("#jed-view", TextArea)
        view.cursor_location = (max(line - 1, 0), 0)
        view.focus()

    def action_save_as(self) -> None:
        """Save the loaded data (a file, edited text or a chip read) under a
        name the user picks; the new file becomes the open one."""
        src = self._data_path
        if not src:
            self.log_action("[yellow]SAVE  no data loaded[/]")
            return
        default = f"{self._read_from}{src.suffix}" if self._read_from else src.name
        # Editable text is saved as it stands on screen, edits included.
        text = self.query_one("#jed-view", TextArea).text if self._saved_text is not None else None

        def _on_save(save_path: Path | None) -> None:
            if not save_path:
                return
            import shutil

            try:
                if text is not None:
                    save_path.write_text(text)
                else:
                    shutil.copy2(src, save_path)
            except OSError as exc:
                self.log_action(f"[red]SAVE  failed:[/]  {exc}")
                return
            self._state["last_directory"] = str(save_path.parent)
            _save_state(self._state)
            self._data_path = save_path
            self._file_label = str(save_path)
            self._read_from = None
            self._update_subtitle()
            self.refresh_bindings()  # Compile shows for a .pld only
            self.log_action(f"[green]SAVE  OK[/]  → {save_path}")
            if text is not None:
                self._load_hex(save_path)  # retitle, and pick up a .jed beside the new name

        self.push_screen(FilePickerScreen(start_path=self.get_last_directory(), save_name=default), _on_save)

    def write_source_problem(self, ic_name: str) -> str | None:
        """Why the loaded data must not be written to *ic_name*, or None.

        Checked before the confirmation step, so nothing is erased for a file
        that cannot fit. write_device checks again before minipro runs.
        """
        from minigecko.core.device_db import get_device
        from minigecko.core.jedec import check_jed_for_chip
        from minigecko.core.minipro import format_for_device

        if not self._data_path:
            return "no data loaded: open a .jed file with f first" \
                if format_for_device(ic_name) == "JED" else "no data loaded"
        if format_for_device(ic_name) != "JED":
            return None
        fuses = (get_device(ic_name) or {}).get("code_memory_size") or 0
        return check_jed_for_chip(self._data_path, ic_name, fuses)

    def run_write_to_device_op(self, ic_name: str, verify: bool = True) -> None:
        src = self._data_path
        if not src:
            self.log_action("[yellow]WRITE  no data loaded[/]")
            return
        self._do_write_device(ic_name, src, verify)

    @work(thread=True)
    def _do_write_device(self, ic_name: str, path: Path, verify: bool) -> None:
        """Write *path*; minipro reads the chip back itself when *verify* is set."""
        from minigecko.core import write_device

        self._log(f"[cyan]WRITE[/]  {ic_name} ← {path.name} …")
        result = write_device(ic_name, path, verify=verify, progress_cb=self._make_progress_cb())
        self.call_from_thread(self._hide_progress)
        if not result.ok:
            failed = next(
                (ln for ln in result.output.splitlines() if "Verification failed" in ln), None
            )
            if failed:
                self._log(f"[red]WRITE  {ic_name} written but VERIFY FAILED:[/]  {failed.strip()}")
            else:
                self._log(f"[red]WRITE  {ic_name} FAILED:[/]  {result.output}")
            return
        if verify:
            self._log(f"[green]WRITE  {ic_name} OK[/]  read back and verified")
        else:
            self._log(f"[green]WRITE  {ic_name} OK[/]  [yellow]not verified[/]")

    def _run_verify_in_thread(self, ic_name: str, reference: Path) -> None:
        """Called from a worker thread, runs verify without spawning another thread."""
        import tempfile
        from minigecko.core import read_device

        tmp: Path | None = None
        try:
            fd, tmp_str = tempfile.mkstemp(prefix="minigecko_verify_", suffix=".bin")
            os.close(fd)
            tmp = Path(tmp_str)
            self._log(f"[cyan]VERIFY[/]  {ic_name} vs {reference.name} …")
            result = read_device(ic_name, tmp)
            if not result.ok:
                self._log(f"[red]VERIFY  {ic_name} read failed:[/]  {result.output}")
                return
            device_bytes = tmp.read_bytes()
            ref_bytes = reference.read_bytes()
            if len(device_bytes) != len(ref_bytes):
                self._log(
                    f"[yellow]VERIFY  {ic_name} size mismatch:[/]"
                    f"  device {len(device_bytes):,} B  vs  file {len(ref_bytes):,} B"
                )
                return
            diffs = sum(a != b for a, b in zip(device_bytes, ref_bytes))
            size = len(device_bytes)
            if diffs == 0:
                self._log(f"[green]VERIFY  {ic_name} OK[/]  identical ({size:,} B)")
            else:
                pct = diffs / size * 100
                self._log(f"[red]VERIFY  {ic_name} FAIL:[/]  {diffs:,} / {size:,} B differ ({pct:.1f}%)")
        except Exception as exc:
            self._log(f"[red]VERIFY  {ic_name} error:[/]  {exc}")
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)

    def run_blank_check_op(self, ic_name: str) -> None:
        self._do_blank_check(ic_name)

    @work(thread=True)
    def _do_blank_check(self, ic_name: str) -> None:
        self._blank_check_and_log(ic_name)

    def _blank_check_and_log(self, ic_name: str) -> None:
        """Blank-check *ic_name* and log the verdict (call from a worker thread)."""
        from minigecko.core import checked_blank_check

        self._log(f"[cyan]BLANK CHECK[/]  {ic_name} …  (contact check first)")
        verdict, detail = checked_blank_check(ic_name)
        if verdict == "blank":
            self._log(f"[green]BLANK CHECK  {ic_name}: blank[/]  {detail}")
        elif verdict == "not blank":
            self._log(f"[yellow]BLANK CHECK  {ic_name}: not blank[/]  {detail}")
        else:
            self._log(
                f"[red]BLANK CHECK  {ic_name} FAILED:[/]  {detail}  "
                f"(this says nothing about the chip's contents)"
            )

    def run_erase_op(self, ic_name: str, blank_check_after: bool = False, read_after: bool = False) -> None:
        if read_after and not self._may_discard("erase_read", "Erase"):
            return
        self._do_erase(ic_name, blank_check_after, read_after)

    @work(thread=True)
    def _do_erase(self, ic_name: str, blank_check_after: bool, read_after: bool) -> None:
        import tempfile
        from minigecko.core import erase_device, read_device

        self._log(f"[cyan]ERASE[/]  {ic_name} …")
        result = erase_device(ic_name, progress_cb=self._make_progress_cb())
        self.call_from_thread(self._hide_progress)
        if not result.ok:
            if "can't be erased" in result.output.lower() or "cannot be erased" in result.output.lower():
                self._log(
                    f"[yellow]ERASE  {ic_name}:[/]  This chip requires UV light to erase "
                    f"(27C-series are UV EPROMs, not EEPROMs). "
                    f"Use a UV eraser lamp (~253 nm, ~30 min)."
                )
            else:
                self._log(f"[red]ERASE  {ic_name} FAILED:[/]  {result.output}")
            return
        self._log(f"[green]ERASE  {ic_name} OK[/]")
        if blank_check_after:
            self._blank_check_and_log(ic_name)
        if read_after:
            fd, tmp_str = tempfile.mkstemp(prefix=f"minigecko_{ic_name}_", suffix=".bin")
            os.close(fd)
            tmp = Path(tmp_str)
            self._log(f"[cyan]READ[/]  {ic_name} after erase …")
            r = read_device(ic_name, tmp)
            if r.ok:
                self.call_from_thread(self._on_read_done, ic_name, tmp)
            else:
                tmp.unlink(missing_ok=True)
                self._log(f"[red]READ  {ic_name} FAILED:[/]  {r.output}")

    def run_compare_op(self, ic_name: str, reference: Path) -> None:
        self.log_action(f"[cyan]COMPARE[/]  {ic_name} vs {reference.name} …")
        self._do_compare(ic_name, reference)

    @work(thread=True)
    def _do_compare(self, ic_name: str, reference: Path) -> None:
        self._run_verify_in_thread(ic_name, reference)

    def action_help(self) -> None:
        if not is_manual_cached():
            self.log_action("[dim]HELP  loading user manual…[/]")
        self.push_screen(HelpScreen())
