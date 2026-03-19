"""
minigecko.core.emulator
~~~~~~~~~~~~~~~~~~~
Fake minipro transport for offline / gym-mode development.

Activated automatically when MINIGECKO_EMULATE=1 is set in the environment.
Implements the same (args, input_data) -> MiniproResult interface as the
real subprocess transport so callers are unaware of the swap.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .minipro import MiniproResult

# ---------------------------------------------------------------------------
# Intel HEX fixture data
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Map chip name substrings → fixture binary files (raw flash dumps)
_FIXTURES: dict[str, str] = {
    "atmega328": "atmega328.hex",
    "atmega8":   "atmega8.hex",
    "mega2560":  "mega2560.hex",
}


def _load_fixture(path: Path, size: int) -> bytes:
    """Load a raw binary fixture file, padded/truncated to `size` bytes."""
    raw = path.read_bytes()
    return (raw + b"\xff" * size)[:size]


def _fixture_for(device: str) -> Path | None:
    dl = device.lower()
    for key, fname in _FIXTURES.items():
        if key in dl:
            p = _DATA_DIR / fname
            return p if p.exists() else None
    return None

# ---------------------------------------------------------------------------
# Static device list (~10 common chips)
# ---------------------------------------------------------------------------

_DEVICES: list[str] = [
    "AT28C256",
    "AT28C64",
    "27C256",
    "27C512",
    "W25Q32",
    "W25Q64",
    "SST39SF040",
    "AT89C51",
    "AT89C52",
    "GAL22V10",
]

# Approximate sizes in bytes for plausible read output
_DEVICE_SIZES: dict[str, int] = {
    "AT28C256":  32_768,
    "AT28C64":    8_192,
    "27C256":    32_768,
    "27C512":    65_536,
    "W25Q32":   4_194_304,
    "W25Q64":   8_388_608,
    "SST39SF040": 524_288,
    "AT89C51":    4_096,
    "AT89C52":    8_192,
    "GAL22V10":     256,
}
_DEFAULT_SIZE = 32_768


def _size_for(device: str) -> int:
    for name, sz in _DEVICE_SIZES.items():
        if name.upper() in device.upper():
            return sz
    return _DEFAULT_SIZE


# ---------------------------------------------------------------------------
# Individual operation handlers
# ---------------------------------------------------------------------------

def _emu_detect() -> MiniproResult:
    return MiniproResult(
        ok=True,
        stdout="Found TL866II+ 4.2.132\n",
    )


def _emu_list(filter_str: str) -> MiniproResult:
    devices = _DEVICES
    if filter_str:
        devices = [d for d in devices if filter_str.upper() in d.upper()]
    return MiniproResult(ok=True, stdout="\n".join(devices) + "\n")


def _emu_read(device: str, output_path: str) -> MiniproResult:
    size    = _size_for(device)
    fixture = _fixture_for(device)
    if fixture:
        data = _load_fixture(fixture, size)
        source = f"fixture {fixture.name}"
    else:
        data   = b"\xff" * size
        source = "0xFF fill"
    Path(output_path).write_bytes(data)
    return MiniproResult(
        ok=True,
        stdout=f"Read {len(data)} bytes from {device} ({source}, emulated)\n",
    )


def _emu_write(device: str) -> MiniproResult:
    time.sleep(0.1)  # simulate brief operation
    return MiniproResult(ok=True, stdout=f"Write to {device} OK (emulated)\n")


def _emu_verify(device: str) -> MiniproResult:
    return MiniproResult(ok=True, stdout=f"Verify {device} OK (emulated)\n")


def _emu_erase(device: str) -> MiniproResult:
    return MiniproResult(ok=True, stdout=f"Erase {device} OK (emulated)\n")


def _emu_logic_test(device: str) -> MiniproResult:
    return MiniproResult(ok=True, stdout=f"Logic/RAM test {device}: all cells OK (emulated)\n")


def _emu_pin_check(device: str) -> MiniproResult:
    return MiniproResult(ok=True, stdout=f"Pin check {device}: all pins OK (emulated)\n")


def _emu_blank_check(device: str) -> MiniproResult:
    fixture = _fixture_for(device)
    if fixture:
        return MiniproResult(
            ok=False,
            stderr=f"Blank check {device}: device is NOT blank (fixture data present, emulated)\n",
        )
    return MiniproResult(ok=True, stdout=f"Blank check {device}: all bytes 0xFF (emulated)\n")


# ---------------------------------------------------------------------------
# Transport entry point
# ---------------------------------------------------------------------------

def emulate(args: list[str], input_data: Optional[bytes] = None, progress_cb=None) -> MiniproResult:
    """Fake transport: parse minipro args and return canned results."""
    # Detect: minipro --version
    if "--version" in args or "-k" in args:
        return _emu_detect()

    # List: minipro -l [filter]
    if "-l" in args:
        idx = args.index("-l")
        filter_str = args[idx + 1] if idx + 1 < len(args) else ""
        return _emu_list(filter_str)

    # Device operations: minipro -p <device> ...
    if "-p" in args:
        idx = args.index("-p")
        device = args[idx + 1] if idx + 1 < len(args) else "UNKNOWN"

        if "-r" in args:
            out_idx = args.index("-r")
            output_path = args[out_idx + 1] if out_idx + 1 < len(args) else "/tmp/emu_out.bin"
            return _emu_read(device, output_path)

        if "-w" in args:
            return _emu_write(device)

        if "-m" in args:
            return _emu_verify(device)

        if "-E" in args:
            return _emu_erase(device)

        if "-b" in args:
            return _emu_blank_check(device)

        if "-z" in args:
            return _emu_pin_check(device)

        if "-T" in args:
            return _emu_logic_test(device)

    return MiniproResult(ok=False, stderr=f"emulator: unrecognized args: {args}")
