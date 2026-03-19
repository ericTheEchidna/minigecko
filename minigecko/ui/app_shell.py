"""Main Textual application shell for MiniGecko."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from minigecko import __version__
from minigecko.ui.hexdump import _MAX_BYTES, _iter_hexdump
from minigecko.ui.modals import ChipSelectScreen, FilePickerScreen, ICOpsScreen, infer_chip_type
from minigecko.ui.panels import ActionLogPanel, HexPanel, ICInfoPanel
from minigecko.ui.state import _load_state, _save_state
from minigecko.ui.toolbar import Toolbar
from minigecko.ui.widgets import ResizeHandle, VResizeHandle

logger = logging.getLogger(__name__)


class MinigeckoApp(App):
    """MiniGecko open source programmer suite."""

    TITLE = f"minigecko v{__version__}"

    DEFAULT_CSS = """
    #right-panel { width: 1fr; height: 1fr; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("f", "file", "File"),
        Binding("s", "select_ic", "Select IC"),
        Binding("d", "ic_ops", "IC Ops"),
        Binding("v", "tools", "Tools"),
        Binding("h", "help", "Help"),
        Binding("ctrl+d", "toggle_dark", "Theme", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+p", "command_palette", "Commands", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._state = _load_state()
        self._programmer_label = "detecting…"
        self._file_label: str | None = None
        self._data_path: Path | None = None
        self._selected_ic: str | None = None

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
            return "device read"
        return "(no file loaded)"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Toolbar()
        with Horizontal(id="body"):
            panel = HexPanel()
            panel.styles.width = self._state["hex_panel_width"]
            yield panel
            yield ResizeHandle()
            with Vertical(id="right-panel"):
                yield ICInfoPanel()
                yield VResizeHandle()
                yield ActionLogPanel()
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(ICInfoPanel).styles.height = self._state["info_panel_height"]
        from minigecko.core import set_binary_path

        set_binary_path(self._state.get("minipro_path", ""))
        self._poll_programmer()
        self._preload_device_db()
        self.query_one("#hex-log").focus()

    @work(thread=True)
    def _poll_programmer(self) -> None:
        from minigecko.core import detect_programmer, is_emulated

        emulated = is_emulated()
        info = detect_programmer()
        if info.connected:
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

    def action_file(self) -> None:
        start = self.get_last_directory()

        def _on_file(path: Path | None) -> None:
            if path:
                self._state["last_directory"] = str(path.parent)
                _save_state(self._state)
                self._file_label = str(path)
                self._data_path = path
                self._update_subtitle()
                self.log_action(f"[green]FILE  opened[/]  {path.name}  ({path.stat().st_size:,} B)")
                self._load_hex(path)

        self.push_screen(FilePickerScreen(start_path=start), _on_file)

    @work(thread=True)
    def _load_hex(self, path: Path) -> None:
        panel = self.query_one(HexPanel)
        self.call_from_thread(panel.clear)

        try:
            data = path.read_bytes()
        except OSError as exc:
            self.call_from_thread(panel.append_line, f"Error: {exc}")
            return

        truncated = len(data) > _MAX_BYTES
        if truncated:
            data = data[:_MAX_BYTES]

        for line in _iter_hexdump(data):
            self.call_from_thread(panel.append_line, line)

        if truncated:
            self.call_from_thread(panel.append_line, f"\n[truncated — showing first {_MAX_BYTES // 2**20} MB]")

        self.call_from_thread(panel.scroll_top)

    def save_panel_width(self) -> None:
        panel = self.query_one(HexPanel)
        self._state["hex_panel_width"] = int(panel.styles.width.value)  # type: ignore[union-attr]
        _save_state(self._state)

    def save_info_panel_height(self) -> None:
        panel = self.query_one(ICInfoPanel)
        self._state["info_panel_height"] = int(panel.styles.height.value)  # type: ignore[union-attr]
        _save_state(self._state)

    def _open_chip_select(self) -> None:
        def _on_selected(chip: str | None) -> None:
            if chip:
                self._selected_ic = chip
                self.query_one("#btn-select-ic", Static).update(f"Selected IC: {chip}")
                btn = self.query_one("#btn-ic-ops", Static)
                btn.remove_class("tb-btn-disabled")
                btn.add_class("tb-btn")
                self.query_one(ICInfoPanel).show(chip)
                self.log_action(f"[green]IC  selected[/]  {chip}")

        self.push_screen(ChipSelectScreen(), _on_selected)

    def action_select_ic(self) -> None:
        self._open_chip_select()

    def on_click(self, event) -> None:
        result = self.screen.get_widget_at(*event.screen_offset)
        widget = result[0] if result else None
        if widget:
            wid = getattr(widget, "id", None)
            if wid == "btn-select-ic":
                self._open_chip_select()
            elif wid == "btn-ic-ops" and self._selected_ic:
                self.action_ic_ops()

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == "ic_ops":
            return bool(self._selected_ic)
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
        self._do_read(ic_name)

    @work(thread=True)
    def _do_read(self, ic_name: str) -> None:
        import tempfile
        from minigecko.core import read_device

        fd, tmp_str = tempfile.mkstemp(prefix=f"minigecko_{ic_name}_", suffix=".bin")
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
        self.log_action(f"[green]READ  {ic_name} OK[/]  {size:,} B")
        self._data_path = path
        self._load_hex(path)

    def run_write_to_file_op(self) -> None:
        src = self._data_path
        if not src:
            self.log_action("[yellow]SAVE  no data loaded[/]")
            return

        def _on_save(save_path: Path | None) -> None:
            if save_path:
                import shutil

                shutil.copy2(src, save_path)
                self._data_path = save_path
                self._file_label = str(save_path)
                self._update_subtitle()
                self.log_action(f"[green]SAVE  OK[/]  → {save_path.name}")

        self.push_screen(FilePickerScreen(start_path=Path(self._state.get("last_directory", str(Path.home())))), _on_save)

    def run_write_to_device_op(self, ic_name: str, verify_after: bool = False) -> None:
        src = self._data_path
        if not src:
            self.log_action("[yellow]WRITE  no data loaded[/]")
            return
        self._do_write_device(ic_name, src, verify_after)

    @work(thread=True)
    def _do_write_device(self, ic_name: str, path: Path, verify_after: bool) -> None:
        from minigecko.core import write_device

        self._log(f"[cyan]WRITE[/]  {ic_name} ← {path.name} …")
        result = write_device(ic_name, path, progress_cb=self._make_progress_cb())
        self.call_from_thread(self._hide_progress)
        if not result.ok:
            self._log(f"[red]WRITE  {ic_name} FAILED:[/]  {result.output}")
            return
        self._log(f"[green]WRITE  {ic_name} OK[/]")
        if verify_after:
            self._run_verify_in_thread(ic_name, path)

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
        from minigecko.core import blank_check_device

        self._log(f"[cyan]BLANK CHECK[/]  {ic_name} …")
        result = blank_check_device(ic_name)
        if result.ok:
            self._log(f"[green]BLANK CHECK  {ic_name} OK[/]  all 0xFF")
        else:
            self._log(f"[yellow]BLANK CHECK  {ic_name}:[/]  not blank")

    def run_erase_op(self, ic_name: str, blank_check_after: bool = False, read_after: bool = False) -> None:
        self._do_erase(ic_name, blank_check_after, read_after)

    @work(thread=True)
    def _do_erase(self, ic_name: str, blank_check_after: bool, read_after: bool) -> None:
        import tempfile
        from minigecko.core import blank_check_device, erase_device, read_device

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
            self._log(f"[cyan]BLANK CHECK[/]  {ic_name} …")
            bc = blank_check_device(ic_name)
            if bc.ok:
                self._log(f"[green]BLANK CHECK  {ic_name} OK[/]  all 0xFF")
            else:
                self._log(f"[yellow]BLANK CHECK  {ic_name}:[/]  not blank")
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

    def action_tools(self) -> None:
        self.log_action("[dim]TOOLS  not implemented yet[/]")

    def action_help(self) -> None:
        self.log_action("[dim]HELP  not implemented yet[/]")
