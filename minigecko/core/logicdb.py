"""
minigecko.core.logicdb
~~~~~~~~~~~~~~~~~~
Parser for minipro's logicic.xml — the database of logic IC test vectors.

The XML is shipped with minipro and installed to /usr/local/share/minipro/
(or $MINIPRO_HOME).  Each <ic> element defines a set of test vectors that
minipro drives via the programmer's ZIF socket when ``minipro -p <device> -T``
is invoked.

This module exposes the database for listing, searching, and previewing
logic IC vectors in the TUI and CLI without requiring hardware.
"""

from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class LogicIC:
    """A logic IC entry from logicic.xml."""
    name: str
    aliases: list[str] = field(default_factory=list)
    voltage: str = ""
    pins: int = 0
    vectors: list[str] = field(default_factory=list)

    @property
    def all_names(self) -> list[str]:
        """Primary name plus all aliases."""
        return [self.name] + self.aliases

    @property
    def vector_count(self) -> int:
        return len(self.vectors)


# ---------------------------------------------------------------------------
# XML location
# ---------------------------------------------------------------------------

_SEARCH_PATHS = [
    "/usr/local/share/minipro/logicic.xml",
    "/usr/share/minipro/logicic.xml",
]


def _find_logicic_xml() -> Path | None:
    """Locate logicic.xml on the system."""
    # $MINIPRO_HOME takes priority
    env = os.environ.get("MINIPRO_HOME")
    if env:
        candidate = Path(env) / "logicic.xml"
        if candidate.is_file():
            return candidate

    for p in _SEARCH_PATHS:
        candidate = Path(p)
        if candidate.is_file():
            return candidate

    return None


# ---------------------------------------------------------------------------
# XML parsing
# ---------------------------------------------------------------------------

def _parse_logicic_xml(path: Path) -> list[LogicIC]:
    """Parse a logicic.xml file and return all IC entries."""
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return []

    ics: list[LogicIC] = []
    for ic_elem in tree.iter("ic"):
        raw_name = ic_elem.get("name", "")
        if not raw_name:
            continue

        names = [n.strip() for n in raw_name.split(",") if n.strip()]
        if not names:
            continue

        voltage = ic_elem.get("voltage", "")
        try:
            pins = int(ic_elem.get("pins", "0"))
        except ValueError:
            pins = 0

        vectors: list[str] = []
        for vec_elem in ic_elem.findall("vector"):
            text = vec_elem.text
            if text:
                vectors.append(text.strip())

        ics.append(LogicIC(
            name=names[0],
            aliases=names[1:],
            voltage=voltage,
            pins=pins,
            vectors=vectors,
        ))

    return ics


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def list_logic_ics() -> list[LogicIC]:
    """Return all logic IC entries from logicic.xml, cached after first call."""
    path = _find_logicic_xml()
    if path is None:
        logger.warning("logicic.xml not found — logic IC database unavailable")
        return []
    return _parse_logicic_xml(path)


@lru_cache(maxsize=1)
def _build_index() -> dict[str, LogicIC]:
    """Build a case-insensitive name → LogicIC lookup dict."""
    index: dict[str, LogicIC] = {}
    for ic in list_logic_ics():
        for name in ic.all_names:
            key = name.upper()
            if key not in index:
                index[key] = ic
    return index


def find_logic_ic(name: str) -> LogicIC | None:
    """Look up a logic IC by name or alias (case-insensitive)."""
    return _build_index().get(name.upper())


def logicic_xml_path() -> Path | None:
    """Return the path to logicic.xml, or None if not found."""
    return _find_logicic_xml()
