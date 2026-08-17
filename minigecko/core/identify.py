"""
minigecko.core.identify
~~~~~~~~~~~~~~~~~~~~~~~
Non-destructive identification of ICs whose markings are unreadable.

The engine narrows minipro's device catalogue using what the user can see
(pin count, package presentation, surviving marking characters), then
optionally confirms with a single read-only chip-ID probe.

Hardware access is injected: `identify()` touches the programmer only when a
probe callable is passed in.
"""

from __future__ import annotations

import fnmatch
import logging
import re

logger = logging.getLogger(__name__)

# Package families that seat directly in a DIP ZIF socket.
DIP_FAMILIES = frozenset({"DIP", "PDIP", "CDIP", "SDIP"})

_PACKAGE_RE = re.compile(r"^([A-Za-z]+)(\d+)")

# Bounds for trusting the numeric pin_count field as a real pin count.
_MIN_PINS = 8
_MAX_PINS = 48


def parse_package(package: str) -> tuple[str | None, int | None]:
    """
    Split a minipro package string into (family, pin count).

    Returns (None, None) when the string carries neither, e.g. "" or "OC".
    Trailing qualifiers such as "(ADP:Pin9to1)" or "(recommend)" are ignored.
    """
    match = _PACKAGE_RE.match(package or "")
    if match is None:
        return None, None
    return match.group(1).upper(), int(match.group(2))


def package_family(entry: dict) -> str | None:
    """Package family for a device_db entry, or None when unknown."""
    return parse_package(entry.get("package", ""))[0]


def socket_pins(entry: dict) -> int | None:
    """
    Resolve how many socket pins a device_db entry occupies.

    The package string is authoritative: the numeric ``pin_count`` field is
    scrambled for non-DIP parts (33 means BGA48, 34 means BGA63, 63 means
    PLCC32).  ``pin_count`` is only consulted when the package string is
    empty, which is the case for logicic.xml entries where it is reliable.
    """
    _, pins = parse_package(entry.get("package", ""))
    if pins is not None:
        return pins

    raw = entry.get("pin_count") or 0
    if _MIN_PINS <= raw <= _MAX_PINS and raw % 2 == 0:
        return int(raw)
    return None


def marking_matches(marking: str, names: list[str]) -> bool:
    """
    Test a surviving-marking fragment against a device's names.

    Syntax is shell-glob and case-insensitive: ``?`` matches one character,
    ``*`` matches any run.  A fragment with no wildcards is treated as a
    substring match, so "74LS" matches "SN74LS00" the way a user expects.
    An empty or whitespace-only fragment matches everything.
    """
    pattern = (marking or "").strip().upper()
    if not pattern:
        return True

    if "*" not in pattern and "?" not in pattern:
        return any(pattern in (name or "").upper() for name in names)

    return any(fnmatch.fnmatchcase((name or "").upper(), pattern) for name in names)
