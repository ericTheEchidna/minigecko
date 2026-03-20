"""
minigecko.core.minipro
~~~~~~~~~~~~~~~~~~
Thin bridge over the minipro CLI.  Every public function returns a
MiniproResult so callers never have to parse raw subprocess output.

Transport is intentionally swappable: when direct libminipro bindings
arrive they can replace run_minipro() without touching anything above.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# Callback: (percent: int | None, label: str) -> None
# percent=None means indeterminate (operation started, no % yet)
ProgressCallback = Optional[Callable[[Optional[int], str], None]]


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class MiniproResult:
    """Unified return value from every minipro operation."""
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    data: dict = field(default_factory=dict)

    @property
    def output(self) -> str:
        return (self.stdout + "\n" + self.stderr).strip()

    def __bool__(self) -> bool:
        return self.ok


# ---------------------------------------------------------------------------
# Device info
# ---------------------------------------------------------------------------

@dataclass
class ProgrammerInfo:
    """Info reported by `minipro -D`."""
    connected: bool
    firmware: str = ""
    hardware: str = ""
    raw: str = ""


@dataclass
class ChipDevice:
    """A device entry from `minipro -l`."""
    name: str
    family: str = ""

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_override_binary: Optional[str] = None


def set_binary_path(path: str) -> None:
    """Override the minipro binary path (empty string = revert to PATH lookup)."""
    global _override_binary
    _override_binary = path.strip() or None


def _minipro_binary() -> Optional[str]:
    """Return the path to the minipro binary, or None if not found."""
    if _override_binary:
        return _override_binary if shutil.os.path.isfile(_override_binary) else None
    return shutil.which("minipro")


def _run_subprocess(
    args: list[str],
    input_data: Optional[bytes] = None,
    progress_cb: ProgressCallback = None,
) -> MiniproResult:
    """Execute minipro with *args* via subprocess and return a MiniproResult."""
    binary = _minipro_binary()
    if binary is None:
        return MiniproResult(
            ok=False,
            stderr="minipro not found. Install it from https://gitlab.com/DavidGriffith/minipro",
        )

    cmd = [binary] + args

    if progress_cb is None:
        try:
            proc = subprocess.run(cmd, capture_output=True, input=input_data, timeout=120)
            return MiniproResult(
                ok=proc.returncode == 0,
                stdout=proc.stdout.decode(errors="replace"),
                stderr=proc.stderr.decode(errors="replace"),
                returncode=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return MiniproResult(ok=False, stderr="minipro timed out after 120 s")
        except OSError as exc:
            return MiniproResult(ok=False, stderr=f"OS error: {exc}")

    # --- Streaming path: parse \r-delimited progress from stderr ---
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE if input_data else None,
        )
    except OSError as exc:
        return MiniproResult(ok=False, stderr=f"OS error: {exc}")

    if input_data:
        proc.stdin.write(input_data)
        proc.stdin.close()

    stdout_chunks: list[bytes] = []

    def _read_stdout() -> None:
        stdout_chunks.append(proc.stdout.read())

    t_stdout = threading.Thread(target=_read_stdout, daemon=True)
    t_stdout.start()

    stderr_lines: list[str] = []
    buf = ""
    try:
        while True:
            ch = proc.stderr.read(1)
            if not ch:
                break
            c = ch.decode(errors="replace")
            if c == "\r":
                clean = _ANSI_RE.sub("", buf).strip()
                if clean:
                    m = re.search(r"(\d+)%", clean)
                    progress_cb(int(m.group(1)) if m else None, clean)
                buf = ""
            elif c == "\n":
                clean = _ANSI_RE.sub("", buf).strip()
                if clean:
                    stderr_lines.append(clean)
                buf = ""
            else:
                buf += c
        if buf.strip():
            stderr_lines.append(_ANSI_RE.sub("", buf).strip())
    except OSError:
        pass

    try:
        proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
        return MiniproResult(ok=False, stderr="minipro timed out after 120 s")

    t_stdout.join(timeout=10)

    return MiniproResult(
        ok=proc.returncode == 0,
        stdout=(stdout_chunks[0] if stdout_chunks else b"").decode(errors="replace"),
        stderr="\n".join(stderr_lines),
        returncode=proc.returncode,
    )


# Module-level transport: swappable for testing / emulation.
# Signature: (args, input_data, progress_cb) -> MiniproResult
_transport: Callable[[list[str], Optional[bytes], ProgressCallback], MiniproResult] = _run_subprocess

if os.environ.get("MINIGECKO_EMULATE", "").strip() == "1":
    from minigecko.core.emulator import emulate as _emulate_transport
    _transport = _emulate_transport


def _run(
    args: list[str],
    input_data: Optional[bytes] = None,
    progress_cb: ProgressCallback = None,
) -> MiniproResult:
    """Dispatch to the active transport (real subprocess or emulator)."""
    return _transport(args, input_data, progress_cb)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """Return True if the minipro binary is on PATH, or emulator is active."""
    if _transport is not _run_subprocess:
        return True
    return _minipro_binary() is not None


def is_emulated() -> bool:
    """Return True when the emulator transport is active (MINIGECKO_EMULATE=1)."""
    return _transport is not _run_subprocess


def detect_programmer() -> ProgrammerInfo:
    """
    Probe the connected programmer.

    Uses ``minipro --version`` which emits a ``Found <model> <fw>`` line
    when a programmer is attached (e.g. ``Found TL866II+ 04.2.132``).
    Falls back to not-connected if the binary is missing or the line is absent.
    """
    result = _run(["--version"])
    text = result.stdout + result.stderr
    fw_match = re.search(r"Found\s+(\S+)\s+([\d.]+)", text)
    if fw_match:
        return ProgrammerInfo(
            connected=True,
            hardware=fw_match.group(1),
            firmware=fw_match.group(2),
            raw=text,
        )
    return ProgrammerInfo(connected=False, raw=text)


def list_devices(filter_str: str = "") -> list[ChipDevice]:
    """
    Return all supported devices, optionally filtered by *filter_str*.
    Wraps `minipro -l` and filters client-side for compatibility.
    """
    result = _run(["-l"])
    if not result.ok:
        return []

    devices: list[ChipDevice] = []
    filt = filter_str.upper()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("Found") or line.startswith("Device"):
            continue
        if filt and filt not in line.upper():
            continue
        devices.append(ChipDevice(name=line))
    return devices


def read_device(
    device: str,
    output_path: Path,
    *,
    format: str = "BIN",
    override_id: bool = True,
    progress_cb: ProgressCallback = None,
) -> MiniproResult:
    """
    Read *device* and write to *output_path*.

    Args:
        device:      minipro device string, e.g. "AT28C256@DIP28"
        output_path: destination file
        format:      "BIN" (default, no -f needed) or "IHEX"
        override_id: pass -y to ignore chip ID mismatch (default True)
    """
    args = ["-p", device, "-r", str(output_path)]
    if format.upper() != "BIN":
        args += ["-f", format.lower()]
    if override_id:
        args.append("-y")
    return _run(args, progress_cb=progress_cb)


def write_device(
    device: str,
    input_path: Path,
    *,
    format: str = "BIN",
    verify: bool = True,
    skip_erase: bool = False,
    progress_cb: ProgressCallback = None,
) -> MiniproResult:
    """
    Write *input_path* to *device*.

    Args:
        device:      minipro device string
        input_path:  source file
        format:      "BIN" or "IHEX"
        verify:      run verify pass after write (default True)
        skip_erase:  skip erase before write (default False)
    """
    args = ["-p", device, "-w", str(input_path), "-y"]
    if format.upper() != "BIN":
        args += ["-f", format.lower()]
    if not verify:
        args.append("-P")  # skip verify
    if skip_erase:
        args.append("-e")  # skip erase
    return _run(args, progress_cb=progress_cb)


def verify_device(device: str, reference_path: Path, *, format: str = "BIN") -> MiniproResult:
    """Verify device contents against *reference_path*."""
    args = ["-p", device, "-m", str(reference_path), "-y"]
    if format.upper() != "BIN":
        args += ["-f", format.lower()]
    return _run(args)


def erase_device(device: str, progress_cb: ProgressCallback = None) -> MiniproResult:
    """Erase *device*."""
    return _run(["-p", device, "-E", "-y"], progress_cb=progress_cb)


def blank_check_device(device: str) -> MiniproResult:
    """Blank-check *device* (verify all bytes are 0xFF)."""
    return _run(["-p", device, "-b", "-y"])


def pin_check_device(device: str) -> MiniproResult:
    """Check for bad pin contact on *device*."""
    return _run(["-p", device, "-z"])


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def logic_test(device: str) -> MiniproResult:
    """
    Run a logic IC test via ``minipro -p <device> -T``.

    On success, ``result.data`` is populated with:
      - ``errors`` (int): number of pin mismatches
      - ``summary`` (str): summary line from minipro
    """
    result = _run(["-p", device, "-T"])
    text = result.stdout + "\n" + result.stderr
    clean = _ANSI_RE.sub("", text)

    # Summary line is on stderr; pin table is on stdout
    clean_err = _ANSI_RE.sub("", result.stderr)
    clean_out = _ANSI_RE.sub("", result.stdout)

    errors = 0
    summary = ""
    for line in clean_err.splitlines():
        m = re.search(r"Logic test (?:failed|successful)(?::\s*(\d+)\s*errors)?", line)
        if m:
            summary = line.strip()
            if m.group(1):
                errors = int(m.group(1))
            break

    detail = "\n".join(l.rstrip() for l in clean_out.splitlines() if l.strip())

    result.data = {"errors": errors, "summary": summary, "detail": detail}
    return result


def get_device_info(device: str) -> MiniproResult:
    """
    Retrieve chip info via ``minipro -d <device>``.

    On success, ``result.data`` is populated with:
      - ``name``, ``package``, ``vector_count``, ``voltage``
    """
    result = _run(["-d", device])
    text = result.stdout + "\n" + result.stderr

    data: dict[str, str | int] = {}
    for line in text.splitlines():
        if line.startswith("Name:"):
            data["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Package:"):
            data["package"] = line.split(":", 1)[1].strip()
        elif "Vector count:" in line:
            try:
                data["vector_count"] = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif "Default VCC voltage:" in line:
            data["voltage"] = line.split(":", 1)[1].strip()

    result.data = data
    return result


def read_pin(device: str, pin_index: int) -> MiniproResult:
    """
    Read a single I/O pin state.  Stub for future libminipro integration.
    Returns result with data["state"] = 0 or 1 when ok.
    """
    return MiniproResult(
        ok=False,
        stderr="Direct pin I/O requires libminipro bindings (not yet implemented)",
    )


def write_pins(device: str, states: dict[int, int]) -> MiniproResult:
    """Drive I/O pins to specified states.  Stub for libminipro integration."""
    return MiniproResult(
        ok=False,
        stderr="Direct pin I/O requires libminipro bindings (not yet implemented)",
    )
