"""
minigecko.core.jedec
~~~~~~~~~~~~~~~~~~~~
Read the parts of a JEDEC (.jed) fuse file that decide whether it fits a chip.

minipro only *warns* when a file's fuse count differs from the selected profile,
then erases and writes anyway (``open_jed_file`` in its ``src/main.c``). So
MiniGecko checks the file itself before handing it over.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_STX, _ETX = "\x02", "\x03"
_FIELD_RE = re.compile(r"\*\s*([A-Z])")


@dataclass
class JedFile:
    device: str            # the file's free-text "Device:" line, "" if absent
    fuse_count: int        # QF
    declared_checksum: int | None   # C field, None if absent
    fuse_checksum: int     # computed from the fuse map


class JedError(ValueError):
    """The file is not a usable JEDEC fuse file."""


def _fuse_checksum(fuses: list[int]) -> int:
    """JEDEC fuse checksum: fuses packed 8 per byte, first fuse in bit 0, summed to 16 bits."""
    total = 0
    for start in range(0, len(fuses), 8):
        byte = 0
        for bit, fuse in enumerate(fuses[start:start + 8]):
            byte |= fuse << bit
        total += byte
    return total & 0xFFFF


def parse_jed(text: str) -> JedFile:
    """Parse JEDEC text. Raises JedError when it has no fuse count or bad fuse rows."""
    if _STX in text:
        text = text.split(_STX, 1)[1]
    body = text.split(_ETX, 1)[0]

    # The design header runs up to the first '*'; its "Device" line names the part.
    header, _, fields_text = body.partition("*")
    device = ""
    for line in header.splitlines():
        m = re.match(r"\s*Device\s*:?\s*(\S+)", line, re.IGNORECASE)
        if m:
            device = m.group(1)
            break

    fuse_count: int | None = None
    default = 0
    declared: int | None = None
    rows: list[tuple[int, str]] = []
    for field in ("*" + fields_text).split("*")[1:]:
        field = field.strip()
        if not field:
            continue
        if field.startswith("QF"):
            fuse_count = int(field[2:].strip())
        elif field.startswith("F"):
            default = int(field[1:].strip() or 0)
        elif field.startswith("C"):
            declared = int(field[1:].strip(), 16)
        elif field.startswith("L"):
            parts = field[1:].split(None, 1)
            bits = re.sub(r"\s", "", parts[1]) if len(parts) > 1 else ""
            if not parts or not parts[0].isdigit() or set(bits) - {"0", "1"}:
                raise JedError(f"bad fuse row: *{field[:40]}")
            rows.append((int(parts[0]), bits))

    if fuse_count is None:
        raise JedError("no fuse count (QF) in the file: is it a JEDEC file?")
    fuses = [default] * fuse_count
    for start, bits in rows:
        if start + len(bits) > fuse_count:
            raise JedError(f"fuse row at {start} runs past the fuse count {fuse_count}")
        fuses[start:start + len(bits)] = [int(b) for b in bits]
    return JedFile(device, fuse_count, declared, _fuse_checksum(fuses))


def check_jed_for_chip(path: Path, chip: str, chip_fuses: int) -> str | None:
    """Return why *path* must not be burned into *chip*, or None when it fits.

    *chip_fuses* is the profile's fuse count (``code_memory_size`` in minipro's
    catalogue).
    """
    try:
        jed = parse_jed(path.read_text(errors="replace"))
    except OSError as exc:
        return f"cannot read {path.name}: {exc}"
    except JedError as exc:
        return f"{path.name}: {exc}"
    made_for = f" (made for {jed.device})" if jed.device else ""
    if chip_fuses and jed.fuse_count != chip_fuses:
        return (
            f"{path.name}{made_for} has {jed.fuse_count} fuses; "
            f"{chip} has {chip_fuses}. Pick the matching chip or file."
        )
    if jed.declared_checksum is not None and jed.declared_checksum != jed.fuse_checksum:
        return (
            f"{path.name} is damaged: its fuse checksum says "
            f"0x{jed.declared_checksum:04X}, the fuses add up to 0x{jed.fuse_checksum:04X}."
        )
    return None
