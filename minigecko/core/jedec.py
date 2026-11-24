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


# ---------------------------------------------------------------------------
# Decompiling with MAME's jedutil (package mame-tools)
# ---------------------------------------------------------------------------

JEDUTIL_MISSING = "Install MAME's jedutil to see logic equations: sudo pacman -S mame-tools"

# jedutil device names by fuse count; ATF parts use their own name when selected.
_JEDUTIL_DEVICE = {2194: "GAL16V8", 2706: "GAL20V8", 5892: "GAL22V10"}


def jedutil_device(fuse_count: int, chip: str = "") -> str | None:
    """jedutil's name for a part with *fuse_count* fuses, or None if it has none."""
    name = _JEDUTIL_DEVICE.get(fuse_count)
    if name and chip.upper().startswith("ATF") and name in ("GAL16V8", "GAL22V10"):
        name = "ATF" + name[3:]
    return name


def _body(text: str) -> str:
    """The fields of a JEDEC file: the text between STX and ETX, right-stripped."""
    body = text.split(_STX, 1)[1] if _STX in text else text
    return body.split(_ETX, 1)[0].rstrip()


def _is_strict(text: str) -> bool:
    """True when every field is closed, so jedutil takes the file as it is."""
    return _body(text).endswith("*")


def strict_jedec(text: str) -> bytes:
    """*text* as a JEDEC file jedutil accepts: every field closed, checksum fixed.

    minipro leaves the last field (``*C…``) without its closing ``*``, and
    MAME's parser rejects that as "Invalid .JED file" (bench, 2026-11-24).
    """
    body = _body(text)
    if not _is_strict(text):
        body += "\r\n*"
    data = (_STX + body + "\r\n" + _ETX).encode("ascii", errors="replace")
    return data + b"%04X\r\n" % (sum(data) & 0xFFFF)


_PIN_DECL_RE = re.compile(r"^\s*PIN\s+(\d+)\s*=\s*(!?)\s*([A-Za-z_]\w*)", re.IGNORECASE | re.MULTILINE)
_TOKEN_RE = re.compile(r"(/?)\b(?:i|o|rf|r)(\d+)\b")


def pin_names(pld_text: str) -> dict[int, tuple[str, bool]]:
    """``{pin: (name, active_low)}`` from a CUPL source's ``Pin N = [!]NAME`` lines."""
    return {int(n): (name, bang == "!") for n, bang, name in _PIN_DECL_RE.findall(pld_text)}


def name_equations(view: str, names: dict[int, tuple[str, bool]]) -> str:
    """Put CUPL signal names into jedutil's equations.

    jedutil names pins by level (``/i1`` = pin 1 low). A pin declared
    ``!WR`` is asserted when low, so ``/i1`` becomes ``WR`` and ``i1`` ``/WR``,
    which is how the source states it.
    """
    def sub(m: re.Match) -> str:
        slash, pin = m.group(1), int(m.group(2))
        if pin not in names:
            return m.group(0)
        name, active_low = names[pin]
        if m.string.startswith(".oe", m.end()):  # output enable: no polarity
            return slash + name
        low = bool(slash) != active_low
        return ("/" if low else "") + name
    return _TOKEN_RE.sub(sub, view)


def decompile(path: Path, chip: str = "") -> tuple[str | None, str]:
    """Logic equations for the .jed at *path*, and a one-line note.

    Returns ``(None, why)`` when they cannot be shown: jedutil missing, an
    unsupported fuse count, or jedutil refusing the file. Never changes *path*.
    """
    import shlex
    import shutil
    import subprocess
    import tempfile

    exe = shutil.which("jedutil")
    if exe is None:
        return None, JEDUTIL_MISSING
    try:
        text = path.read_text(errors="replace")
        jed = parse_jed(text)
    except (OSError, JedError) as exc:
        return None, f"cannot decompile: {exc}"
    device = jedutil_device(jed.fuse_count, chip)
    if device is None:
        return None, f"jedutil has no {jed.fuse_count}-fuse part to decompile this as"

    from minigecko.core.minipro import announce

    # Log the command for the user's own file; jedutil itself reads a fixed copy.
    command = shlex.join(["jedutil", "-view", str(path), device])
    announce(command, "" if _is_strict(text) else (
        "this file's last field lacks its closing *, so jedutil rejects it as it "
        "stands; MiniGecko gave jedutil a fixed copy"
    ))
    with tempfile.NamedTemporaryFile(suffix=".jed") as tmp:
        tmp.write(strict_jedec(text))
        tmp.flush()
        try:
            out = subprocess.run([exe, "-view", tmp.name, device],
                                 capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, f"jedutil failed: {exc}"
    view = (out.stdout + out.stderr).strip()
    if not view or "Fatal error" in view:  # jedutil exits 0 even then
        return None, f"jedutil could not read it: {view.splitlines()[0] if view else 'no output'}"

    note = f"Decompiled as {device} by MAME jedutil."
    pld = next((p for p in (path.with_suffix(".pld"), path.with_suffix(".PLD")) if p.exists()), None)
    if pld is not None:
        names = pin_names(pld.read_text(errors="replace"))
        if names:
            view = name_equations(view, names)
            note += f" Signal names from {pld.name}."
    if not _has_logic(view):
        note += " No logic in it: blank, or read back from a secured chip."
    return view, note


def _has_logic(view: str) -> bool:
    """True when any output equation (not an .oe line) has a right-hand side."""
    for line in view.split("Equations:", 1)[-1].splitlines():
        if "=" in line and ".oe" not in line.split("=", 1)[0]:
            if line.split("=", 1)[1].strip():
                return True
    return False
