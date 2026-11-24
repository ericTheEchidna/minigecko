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
WINE_MISSING = "Wine is not installed: WinCUPL runs under it to compile CUPL .pld files."
UNKNOWN_LANGUAGE = (
    "Not a GALasm or CUPL source: a GALasm file starts with its chip "
    "(GAL16V8, GAL20V8, GAL22V10 or GAL20RA10), a CUPL file declares "
    "'Device …;'."
)

_GALETTE_ERROR_RE = re.compile(r"Error in line (\d+):\s*(.*)")

# WinCUPL under Wine, run as Eric's Forbin80 `pcb/cupl` and Frances `tools/cupl`
# scripts run it: -j JEDEC and -n (name outputs after the source) always, the
# rest from COMPILER_OPTIONS. What each WinCUPL flag writes (probed 2026-11-24,
# WinCUPL's own help text in cupl.exe): -a .abs + .sim (for the simulator),
# -e .mx (expanded macros), -x .doc with expanded product terms, -f fuse plot
# in the .doc; with neither -x nor -f there is no .doc. -m0..-m4 minimisation.
_CUPL_DIR = r"C:\Wincupl\Shared"
_DEFAULT_WINE_PREFIX = Path.home() / ".wine-cupl"

# Compiler options, as UI state stores them. Defaults agreed with Eric
# 2026-11-24: WinCUPL writes .jed and .doc; Galette writes .jed and .chp; the
# security fuse stays off.
DEFAULT_COMPILER_OPTIONS: dict[str, dict] = {
    "galette": {"chp": True, "fus": False, "pin": False, "secure": False},
    "wincupl": {
        "doc_equations": True,   # -x
        "doc_fuse_plot": True,   # -f
        "simulator": False,      # -a: .abs and .sim
        "macros": False,         # -e: .mx
        "minimize": 1,           # -m0 … -m4
    },
}
MINIMIZE_LEVELS = {  # WinCUPL's own words, from cupl.exe
    0: "None (no logic reduction)",
    1: "Quick (default; lowest memory use, fastest)",
    2: "Quine-McCluskey (most memory, slowest)",
    3: "Presto (a trade-off between memory and speed)",
    4: "Espresso (much memory, slow; good for fitter designs)",
}
_options: dict[str, dict] = {k: dict(v) for k, v in DEFAULT_COMPILER_OPTIONS.items()}


def set_compiler_options(options: dict) -> None:
    """Use *options* (as stored in UI state); keys it lacks keep their defaults."""
    global _options
    _options = {
        tool: {**defaults, **(options or {}).get(tool, {})}
        for tool, defaults in DEFAULT_COMPILER_OPTIONS.items()
    }


def galette_flags() -> list[str]:
    """Galette's flags for the current options (it writes .jed always)."""
    o = _options["galette"]
    flags = [] if o["chp"] else ["-c"]
    flags += [] if o["fus"] else ["-f"]
    flags += [] if o["pin"] else ["-p"]
    return flags + (["-s"] if o["secure"] else [])


def galette_outputs() -> list[str]:
    o = _options["galette"]
    return [".jed"] + [f".{k}" for k in ("chp", "fus", "pin") if o[k]]


def wincupl_flags() -> list[str]:
    """WinCUPL's flags for the current options."""
    o = _options["wincupl"]
    flags = ["-j", "-n"]
    flags += ["-a"] if o["simulator"] else []
    flags += ["-x"] if o["doc_equations"] else []
    flags += ["-f"] if o["doc_fuse_plot"] else []
    flags += ["-e"] if o["macros"] else []
    return flags + [f"-m{int(o['minimize'])}"]


def wincupl_outputs() -> list[str]:
    o = _options["wincupl"]
    outputs = [".jed"]
    outputs += [".doc"] if o["doc_equations"] or o["doc_fuse_plot"] else []
    outputs += [".abs", ".sim"] if o["simulator"] else []
    return outputs + ([".mx"] if o["macros"] else [])
_wine_prefix: Path | None = None  # None = _DEFAULT_WINE_PREFIX

# "105:PAGE_CK = = …" names the line; "[0007ca] invalid syntax:  =" the error.
_CUPL_LINE_RE = re.compile(r"^(\d+):", re.MULTILINE)
_CUPL_ERROR_RE = re.compile(r"^\[[0-9a-f]{6}\]\s*(.+)$", re.MULTILINE)
# WinCUPL leaves a scratch file like CB000000 beside the source.
_CUPL_SCRATCH_RE = re.compile(r"^CB\d{6}$")


def set_wine_prefix(path: str) -> None:
    """The Wine prefix that holds WinCUPL (empty string = ~/.wine-cupl)."""
    global _wine_prefix
    _wine_prefix = Path(path).expanduser() if path.strip() else None


def wine_prefix() -> Path:
    return _wine_prefix or _DEFAULT_WINE_PREFIX


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

    Which files each tool writes, and whether Galette sets the security
    fuse, follow the compiler options (see ``set_compiler_options``).
    """
    from minigecko.core.minipro import announce

    try:
        text = path.read_text(errors="replace")
    except OSError as exc:
        return CompileResult(False, f"cannot read {path.name}: {exc}")
    language = pld_language(text)
    if language == CUPL:
        return _compile_cupl(path, text)
    if language != GALASM:
        return CompileResult(False, UNKNOWN_LANGUAGE)

    exe = shutil.which("galette")
    if exe is None:
        return CompileResult(False, GALETTE_MISSING)
    args = galette_flags() + [str(path)]
    announce(shlex.join(["galette"] + args))
    try:
        out = subprocess.run([exe] + args, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CompileResult(False, f"Galette failed: {exc}")
    report = (out.stdout + out.stderr).strip()
    if out.returncode == 0:
        return CompileResult(True, _wrote(path, galette_outputs()))
    m = _GALETTE_ERROR_RE.search(report)
    if m:
        return CompileResult(False, f"line {m.group(1)}: {m.group(2)}", int(m.group(1)))
    lines = report.splitlines()
    return CompileResult(False, lines[-1] if lines else f"Galette exited with status {out.returncode}")


def _compile_cupl(path: Path, text: str) -> CompileResult:
    """Compile a CUPL source with WinCUPL under Wine, beside the source."""
    import os
    import time

    from minigecko.core.minipro import announce

    wine = shutil.which("wine")
    if wine is None:
        return CompileResult(False, WINE_MISSING)
    prefix = wine_prefix()
    exe = prefix / "drive_c" / "Wincupl" / "Shared" / "cupl.exe"
    if not exe.is_file():
        return CompileResult(False, (
            f"WinCUPL is not installed: no cupl.exe at {exe}. If it lives in "
            "another Wine prefix, set wincupl_prefix in the state file."
        ))
    # CUPL reads ASCII only; a UTF-8 dash aborts it with "illegal character".
    for n, line in enumerate(text.splitlines(), start=1):
        if not line.isascii():
            return CompileResult(
                False, f"line {n}: a non-ASCII character; CUPL reads ASCII only", n
            )

    folder = path.parent
    env_vars = {
        "WINEPREFIX": str(prefix),
        "WINEDEBUG": "-all",
        "LIBCUPL": _CUPL_DIR + r"\cupl.dl",
    }
    argv = ["wine", _CUPL_DIR + r"\cupl.exe", *wincupl_flags(), path.stem]
    announce(
        f"cd {shlex.quote(str(folder))} && "
        + " ".join(f"{k}={shlex.quote(v)}" for k, v in env_vars.items())
        + " " + shlex.join(argv)
    )
    scratch_before = {p.name for p in folder.iterdir() if _CUPL_SCRATCH_RE.match(p.name)}
    started = time.time()
    try:
        out = subprocess.run(
            [wine] + argv[1:], cwd=folder, capture_output=True, text=True,
            timeout=120, env={**os.environ, **env_vars},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CompileResult(False, f"WinCUPL failed: {exc}")
    finally:
        for p in folder.iterdir():  # remove only the scratch files this run made
            if _CUPL_SCRATCH_RE.match(p.name) and p.name not in scratch_before:
                p.unlink(missing_ok=True)

    report = out.stdout + out.stderr
    jed = path.with_suffix(".jed")
    if out.returncode == 0 and jed.exists() and jed.stat().st_mtime >= started - 1:
        return CompileResult(True, _wrote(path, wincupl_outputs()))
    error = _CUPL_ERROR_RE.search(report)
    line = _CUPL_LINE_RE.search(report)
    message = error.group(1).strip() if error else f"WinCUPL exited with status {out.returncode}"
    message = re.sub(r"\s+", " ", message)
    if line:
        return CompileResult(False, f"line {line.group(1)}: {message}", int(line.group(1)))
    return CompileResult(False, message)


def _wrote(path: Path, suffixes: list[str]) -> str:
    """'wrote x.jed and x.chp' for the outputs the options asked for."""
    names = [path.stem + sfx for sfx in suffixes]
    listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return f"wrote {listed}"


def compiler_note(text: str) -> str:
    """Plain words for the Source pane: the language and what F9 will run."""
    language = pld_language(text)
    if language == GALASM:
        name, tool, ready = "GALasm", "Galette", shutil.which("galette") is not None
    elif language == CUPL:
        exe = wine_prefix() / "drive_c" / "Wincupl" / "Shared" / "cupl.exe"
        name, tool = "CUPL", "WinCUPL"
        ready = shutil.which("wine") is not None and exe.is_file()
    else:
        return "not GALasm or CUPL, so F9 cannot compile it"
    return f"{name}, F9 compiles with {tool}" + ("" if ready else f" ({tool} not found)")
