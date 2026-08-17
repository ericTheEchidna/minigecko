"""
minigecko.core.identify
~~~~~~~~~~~~~~~~~~~~~~~
Non-destructive identification of ICs whose markings are unreadable.

The engine narrows minipro's device catalogue using what the user can see
(pin count, package presentation, surviving marking characters), then
optionally confirms with a single read-only chip-ID probe.

Hardware access is injected: `identify()` touches the programmer only when a
probe callable is passed in.

device_db entries are shared, cached objects: treat every entry this module
hands out as read-only and never mutate one you did not build yourself.
"""

from __future__ import annotations

import fnmatch
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from types import MappingProxyType

from minigecko.core.device_db import decode_flags, get_db, get_device
from minigecko.core.minipro import ProgrammerInfo, detect_programmer

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
    PLCC32).  ``pin_count`` is only consulted when the package string carries
    no pin count, which is the case for logicic.xml entries where it is
    reliable.
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
    Wildcard fragments match anywhere in the name too, so "74??00" matches
    "SN74LS00" past the manufacturer prefix.  An empty or whitespace-only
    fragment matches everything.
    """
    pattern = (marking or "").strip().upper()
    if not pattern:
        return True

    if "*" not in pattern and "?" not in pattern:
        return any(pattern in (name or "").upper() for name in names)

    if not pattern.startswith("*"):
        pattern = "*" + pattern
    if not pattern.endswith("*"):
        pattern = pattern + "*"

    return any(fnmatch.fnmatchcase((name or "").upper(), pattern) for name in names)


def normalize_chip_id(raw: str) -> str:
    """
    Reduce a chip ID to comparable form: no "0x", upper case, no leading zeros.

    device_db stores 8 hex digits ("0x01007e22") while minipro reports 4 for
    some parts ("0x0108"), so raw string comparison fails.  An all-zero ID
    normalises to "0".
    """
    text = (raw or "").strip().upper()
    if text.startswith("0X"):
        text = text[2:]
    if not text:
        return ""
    return text.lstrip("0") or "0"


def is_id_capable(entry: dict) -> bool:
    """True when the device's hardware flags advertise chip ID support."""
    return any(
        label == "Chip ID" and bool(value)
        for _key, label, value in decode_flags(entry)
    )


@lru_cache(maxsize=1)
def unique_entries() -> tuple[dict, ...]:
    """
    Every distinct device_db entry, once.

    get_db() maps each name variant to a shared entry dict, so iterating its
    values yields the same object many times.
    """
    return tuple({id(v): v for v in get_db().values()}.values())


@lru_cache(maxsize=1)
def chip_id_index() -> Mapping[str, tuple[str, ...]]:
    """
    Reverse index: normalised chip ID -> device names carrying that ID.

    IDs are deliberately non-unique (0x01007e22 is shared by 136 devices), so
    each key holds a group of names, de-duplicated in first-seen order.
    Entries without the has_chip_id flag, and the all-zero placeholder ID, are
    excluded.

    The returned mapping is cached and shared by every caller, so it is
    read-only: a caller wanting to sort or slice a group must copy it first.
    """
    index: dict[str, list[str]] = {}
    zero = normalize_chip_id("0x00000000")

    for entry in unique_entries():
        if not is_id_capable(entry):
            continue
        key = normalize_chip_id(entry.get("chip_id", ""))
        if not key or key == zero:
            continue
        for name in entry.get("canonical_names", []):
            index.setdefault(key, []).append(name)

    logger.debug("chip_id_index: %d distinct IDs", len(index))
    return MappingProxyType(
        {key: tuple(dict.fromkeys(names)) for key, names in index.items()}
    )


def probe_carriers(pin_count: int) -> list[str]:
    """
    Devices usable as an electrical harness for an ID read at *pin_count* pins.

    Eligibility is deliberately strict: an exact pin-count match (the proxy for
    "VCC and GND land on the same socket pins"), a DIP package (a carrier
    defines the socket wiring), chip-ID capability, and not an ISP entry.
    Mismatches are excluded, never merely ranked lower.  A carrier is reported
    under a name that get_device() resolves back to the entry that passed those
    checks; some names are shared by several entries, so the first canonical
    name is not always such a name.
    """
    carriers: list[str] = []
    for entry in unique_entries():
        if entry.get("is_isp"):
            continue
        if socket_pins(entry) != pin_count:
            continue
        if package_family(entry) not in DIP_FAMILIES:
            continue
        if not is_id_capable(entry):
            continue
        name = addressable_name(entry)
        if name:
            carriers.append(name)
    return sorted(carriers)


def addressable_name(entry: dict) -> str | None:
    """
    A canonical name of *entry* that get_device() resolves back to it.

    Preference goes to a name whose own "@PACKAGE" suffix agrees with the
    entry's resolved family and pin count, because the name is what reaches
    ``minipro -p`` and therefore decides which socket pins carry VCC and GND.
    Agreement is with the entry's *own* package, so a SOIC-8 entry keeps a
    SOIC-8 name.  The first merely-resolving name is a last-resort fallback;
    for a carrier, which has already passed the DIP and pin-count checks, it is
    unreachable.
    """
    resolving = [
        name for name in entry.get("canonical_names") or [] if get_device(name) is entry
    ]
    entry_family = package_family(entry)
    pins = socket_pins(entry)

    for name in resolving:
        _, _, suffix = name.partition("@")
        family, name_pins = parse_package(suffix)
        if family is not None and family == entry_family and name_pins == pins:
            return name

    return resolving[0] if resolving else None


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

EVIDENCE_SILICON_ID = "silicon_id"
EVIDENCE_MARKING = "marking"
EVIDENCE_PACKAGE = "package"

CONFIDENCE_ORDER = {"confirmed": 0, "probable": 1, "possible": 2}


@dataclass(frozen=True)
class ChipHint:
    """What the user can see without powering anything."""
    pin_count: int
    via_adapter: bool = False
    marking: str | None = None


@dataclass(frozen=True)
class Evidence:
    """One reason a candidate is plausible, kept as data so the UI can show it."""
    kind: str
    detail: str


@dataclass
class Candidate:
    """A device that could be the chip in the socket, plus why."""
    name: str
    entry: dict  # shared device_db entry, read-only — see the module docstring
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def confidence(self) -> str:
        """
        Derived from which evidence kinds are present.  Fixed three-way rule,
        no numeric weights.
        """
        kinds = {e.kind for e in self.evidence}
        if EVIDENCE_SILICON_ID in kinds:
            return "confirmed"
        if EVIDENCE_MARKING in kinds:
            return "probable"
        return "possible"

    @property
    def sort_key(self) -> tuple[int, str]:
        return CONFIDENCE_ORDER[self.confidence], self.name

    @property
    def evidence_summary(self) -> str:
        """Single-line human-readable joining of all evidence details."""
        return " + ".join(e.detail for e in self.evidence)


@dataclass
class NextStep:
    """A deeper identification pass this stage does not implement yet."""
    label: str
    estimate: str
    stage: int
    available: bool = False


@dataclass
class IdentifyReport:
    """Result of an identification attempt.  "Couldn't tell" is a valid result."""
    candidates: list[Candidate]
    diagnostics: list[str]
    suggested_next: list[NextStep]
    observed_id: str | None = None
    carrier: str | None = None


# ---------------------------------------------------------------------------
# Tier 0 — catalogue filter, no hardware
# ---------------------------------------------------------------------------

def _seats_in_socket(entry: dict, hint: ChipHint) -> bool:
    """
    True when *entry* could physically be the chip the user describes.

    An empty package string means the package is unknown, not that it is
    non-DIP — 259 of 261 logic IC entries are in that group — so unknown
    packages stay eligible in both direct and adapter mode.
    """
    if socket_pins(entry) != hint.pin_count:
        return False
    family = package_family(entry)
    if family is None or family in DIP_FAMILIES:
        return True
    return hint.via_adapter


def tier0_candidates(hint: ChipHint) -> list[Candidate]:
    """
    Filter the catalogue on what the user can see.  Touches no hardware.

    Every surviving entry gets package evidence; those matched by a marking
    fragment additionally get marking evidence, which lifts them to
    "probable".
    """
    marking = (hint.marking or "").strip()
    presentation = "via adapter" if hint.via_adapter else "direct"
    candidates: list[Candidate] = []

    for entry in unique_entries():
        if not _seats_in_socket(entry, hint):
            continue

        names = entry.get("canonical_names") or []
        if not names:
            continue

        if marking and not marking_matches(marking, names):
            continue

        # NOT names[0]: a name can be claimed by another entry, and the name is
        # what later minipro operations are built from.
        name = addressable_name(entry)
        if name is None:
            continue

        evidence = [
            Evidence(
                kind=EVIDENCE_PACKAGE,
                detail=f"{hint.pin_count}-pin {presentation}",
            )
        ]
        if marking:
            evidence.append(
                Evidence(kind=EVIDENCE_MARKING, detail=f"marking matches {marking!r}")
            )

        candidates.append(Candidate(name=name, entry=entry, evidence=evidence))

    candidates.sort(key=lambda c: c.sort_key)
    return candidates


# ---------------------------------------------------------------------------
# Socket geometry
# ---------------------------------------------------------------------------

DEFAULT_SOCKET_WIDTH = 40

_SOCKET_WIDTHS = {
    "TL866A": 40,
    "TL866CS": 40,
    "TL866II+": 40,
    "T48": 40,
    "T56": 48,
}


def socket_width(info: ProgrammerInfo | None = None) -> int:
    """
    Physical pin width of the attached programmer's ZIF socket.

    Falls back to 40 for unknown or absent hardware, which can only
    under-offer pin counts rather than over-offer them.
    """
    if info is None:
        info = detect_programmer()
    if not info.connected:
        return DEFAULT_SOCKET_WIDTH
    return _SOCKET_WIDTHS.get(info.hardware, DEFAULT_SOCKET_WIDTH)
