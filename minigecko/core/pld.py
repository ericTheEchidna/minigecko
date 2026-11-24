"""
minigecko.core.pld
~~~~~~~~~~~~~~~~~~
Compile a PLD source (.pld) to a JEDEC fuse map (.jed).

Galette and WinCUPL both read ``.pld`` files, in different languages. The
file's own text decides which tool it needs; there is no fallback between
them, because neither reads the other's language.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

GALASM = "galasm"
CUPL = "cupl"

# Galette (GALasm language): the first meaningful line names the chip alone.
_GALASM_CHIPS = {"GAL16V8", "GAL20V8", "GAL22V10", "GAL20RA10"}
# CUPL: header fields end in ';', and the device is declared by keyword.
_CUPL_DEVICE_RE = re.compile(r"^\s*device\s+\S+\s*;", re.IGNORECASE | re.MULTILINE)

GALETTE_MISSING = "Galette is not installed: it compiles GALasm .pld files."
CUPL_NOT_BUILT_IN = (
    "This is a CUPL source. Compiling CUPL with WinCUPL is not built into "
    "MiniGecko yet: compile it in WinCUPL, then open the .jed."
)
UNKNOWN_LANGUAGE = (
    "Not a GALasm or CUPL source: a GALasm file starts with its chip "
    "(GAL16V8, GAL20V8, GAL22V10 or GAL20RA10), a CUPL file declares "
    "'Device …;'."
)

_GALETTE_ERROR_RE = re.compile(r"Error in line (\d+):\s*(.*)")


def pld_language(text: str) -> str | None:
    """``"galasm"``, ``"cupl"`` or None for the source *text*."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):  # GALasm comments start with ';'
            continue
        if stripped.upper() in _GALASM_CHIPS:
            return GALASM
        break
    if _CUPL_DEVICE_RE.search(text):
        return CUPL
    return None


@dataclass
class CompileResult:
    """What a compile did: *ok*, a plain-words *message*, and the source
    *line* an error points at (1-based), when the tool names one."""
    ok: bool
    message: str
    line: int | None = None


def compile_pld(path: Path) -> CompileResult:
    """Compile *path* with the tool its language needs, beside the source.

    Galette writes ``<name>.jed`` and ``<name>.chp`` next to *path*; its
    ``.fus`` and ``.pin`` outputs are switched off. MiniGecko never passes
    ``-s``, which would set the security fuse.
    """
    from minigecko.core.minipro import announce

    try:
        text = path.read_text(errors="replace")
    except OSError as exc:
        return CompileResult(False, f"cannot read {path.name}: {exc}")
    language = pld_language(text)
    if language == CUPL:
        return CompileResult(False, CUPL_NOT_BUILT_IN)
    if language != GALASM:
        return CompileResult(False, UNKNOWN_LANGUAGE)

    exe = shutil.which("galette")
    if exe is None:
        return CompileResult(False, GALETTE_MISSING)
    args = ["-f", "-p", str(path)]
    announce(shlex.join(["galette"] + args))
    try:
        out = subprocess.run([exe] + args, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CompileResult(False, f"Galette failed: {exc}")
    report = (out.stdout + out.stderr).strip()
    if out.returncode == 0:
        return CompileResult(True, f"wrote {path.stem}.jed and {path.stem}.chp")
    m = _GALETTE_ERROR_RE.search(report)
    if m:
        return CompileResult(False, f"line {m.group(1)}: {m.group(2)}", int(m.group(1)))
    lines = report.splitlines()
    return CompileResult(False, lines[-1] if lines else f"Galette exited with status {out.returncode}")
