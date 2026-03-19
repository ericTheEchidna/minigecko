"""
minigecko.core.device_db
~~~~~~~~~~~~~~~~~~~~
Parses minipro's infoic.xml and logicic.xml into an in-memory lookup dict.
Loaded once at first access; all public access goes through get_db().
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

MINIPRO_DATA_DIR = Path("/usr/local/share/minipro")
INFOIC_XML       = MINIPRO_DATA_DIR / "infoic.xml"
LOGICIC_XML      = MINIPRO_DATA_DIR / "logicic.xml"

# ---------------------------------------------------------------------------
# Chip type constants
# ---------------------------------------------------------------------------

TYPE_EEPROM = 1
TYPE_MCU    = 2
TYPE_PLD    = 3
TYPE_SRAM   = 4
TYPE_LOGIC  = 5
TYPE_NAND   = 6
TYPE_EMMC   = 7
TYPE_VGA    = 8

_TYPE_LABELS: dict[int, str] = {
    TYPE_EEPROM: "ROM / EEPROM / Flash",
    TYPE_MCU:    "MCU / MPU",
    TYPE_PLD:    "PLD / CPLD",
    TYPE_SRAM:   "SRAM",
    TYPE_LOGIC:  "Logic IC",
    TYPE_NAND:   "NAND Flash",
    TYPE_EMMC:   "eMMC / eSD",
    TYPE_VGA:    "VGA / HDMI",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _type_label(chip_type: int) -> str:
    return _TYPE_LABELS.get(chip_type, f"Type {chip_type}")


def _extract_package(name: str) -> str:
    """Return the @SUFFIX part of a device name, e.g. 'DIP28', or ''."""
    if "@" in name:
        return name.split("@", 1)[1]
    return ""


_MP_ERASE_MASK          = 0x00000010
_MP_ID_MASK             = 0x00000020
_MP_DATA_MEMORY_ADDRESS = 0x00001000
_MP_DATA_BUS_WIDTH      = 0x00002000
_MP_OFF_PROTECT_BEFORE  = 0x00004000
_MP_PROTECT_AFTER       = 0x00008000
_MP_LOCK_BIT_WRITE_ONLY = 0x00040000
_MP_CALIBRATION         = 0x00080000
_MP_SUPPORTED_PROG      = 0x00300000
_MP_REVERSED_PACKAGE    = 0x00000002

_PROG_SUPPORT_LABELS = {0: "ZIF only", 1: "ZIF + ICSP", 2: "ICSP only", 0x80: "Read-only"}


def decode_flags(entry: dict) -> list[tuple[str, str, bool | str]]:
    """
    Return a list of (flag_name, description, value) for every meaningful flag
    in a device entry.  value is bool for on/off flags, str for enum fields.
    """
    try:
        raw = int(entry.get("flags", "0") or "0", 16)
    except ValueError:
        raw = 0

    chip_info = entry.get("chip_info_raw", 0)

    results: list[tuple[str, str, bool | str]] = [
        ("can_erase",          "Erasable",        bool(raw & _MP_ERASE_MASK)),
        ("has_chip_id",        "Chip ID",         bool(raw & _MP_ID_MASK)),
        ("word_size",          "16-bit words",    bool(raw & _MP_DATA_BUS_WIDTH)),
        ("has_data_offset",    "Data offset",     bool(raw & _MP_DATA_MEMORY_ADDRESS)),
        ("off_protect_before", "WP off before",   bool(raw & _MP_OFF_PROTECT_BEFORE)),
        ("protect_after",      "WP on after",     bool(raw & _MP_PROTECT_AFTER)),
        ("lock_bit_write_only","Lock write-once", bool(raw & _MP_LOCK_BIT_WRITE_ONLY)),
        ("has_calibration",    "Calibration",     bool(raw & _MP_CALIBRATION)),
        ("reversed_package",   "Reversed pins",   bool(raw & _MP_REVERSED_PACKAGE)),
        ("can_adjust_vcc",     "Adj. VCC",        chip_info == 0x0006),
        ("can_adjust_vpp",     "Adj. VPP",        chip_info == 0x0007),
        ("prog_support",       "Interface",
            _PROG_SUPPORT_LABELS.get((raw & _MP_SUPPORTED_PROG) >> 20, "R/W")),
    ]
    return results


def _fmt_size(n: int) -> str:
    if n == 0:
        return ""
    if n >= 1024 * 1024:
        return f"{n // (1024 * 1024)} MB"
    if n >= 1024:
        return f"{n // 1024} KB"
    return f"{n} B"


def _make_entry(
    variants: list[str],
    manufacturer: str,
    chip_type: int,
    code_memory_size: int,
    data_memory_size: int,
    pin_count: int,
    protocol_id: str,
    chip_id: str,
    voltages: str,
    flags: str,
    chip_info: str = "",
) -> dict:
    package  = next((_extract_package(v) for v in variants if "@" in v), "")
    is_isp   = any("(ISP)" in v for v in variants)
    try:
        flags_int = int(flags, 16) if flags else 0
    except ValueError:
        flags_int = 0
    try:
        chip_info_int = int(chip_info, 16) if chip_info else 0
    except ValueError:
        chip_info_int = 0
    can_erase = bool(flags_int & 0x00000010)
    return {
        "canonical_names":    variants,
        "manufacturer":       manufacturer,
        "type":               chip_type,
        "type_label":         _type_label(chip_type),
        "code_memory_size":   code_memory_size,
        "data_memory_size":   data_memory_size,
        "size_label":         _fmt_size(code_memory_size),
        "package":            package,
        "pin_count":          pin_count,
        "is_isp":             is_isp,
        "protocol_id":        protocol_id,
        "chip_id":            chip_id,
        "voltages":           voltages,
        "flags":              flags,
        "chip_info_raw":      chip_info_int,
        "can_erase":          can_erase,
    }

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_infoic(path: Path) -> dict[str, dict]:
    db: dict[str, dict] = {}
    try:
        tree = ET.parse(path)
    except Exception:
        return db

    root = tree.getroot()
    database = root.find("database")
    if database is None:
        database = root  # some versions flatten the hierarchy

    for manufacturer in database:
        mfr_name = manufacturer.attrib.get("name", "")
        for ic in manufacturer:
            attrib = ic.attrib
            raw_names = attrib.get("name", "")
            if not raw_names:
                continue
            variants = [v.strip() for v in raw_names.split(",") if v.strip()]

            try:
                chip_type = int(attrib.get("type", "1"))
            except ValueError:
                chip_type = 1

            try:
                code_mem = int(attrib.get("code_memory_size", "0x0"), 16)
            except ValueError:
                code_mem = 0
            try:
                data_mem = int(attrib.get("data_memory_size", "0x0"), 16)
            except ValueError:
                data_mem = 0
            try:
                pkg_raw   = int(attrib.get("package_details", "0x0"), 16)
                pin_count = (pkg_raw >> 24) & 0xFF
            except ValueError:
                pin_count = 0

            entry = _make_entry(
                variants         = variants,
                manufacturer     = mfr_name,
                chip_type        = chip_type,
                code_memory_size = code_mem,
                data_memory_size = data_mem,
                pin_count        = pin_count,
                protocol_id      = attrib.get("protocol_id", ""),
                chip_id          = attrib.get("chip_id", ""),
                voltages         = attrib.get("voltages", ""),
                flags            = attrib.get("flags", ""),
                chip_info        = attrib.get("chip_info", ""),
            )
            for variant in variants:
                db[variant] = entry

    return db


def _parse_logicic(path: Path) -> dict[str, dict]:
    db: dict[str, dict] = {}
    try:
        tree = ET.parse(path)
    except Exception:
        return db

    root = tree.getroot()
    database = root.find("database")
    if database is None:
        database = root

    for manufacturer in database:
        mfr_name = manufacturer.attrib.get("name", "Logic Ic")
        for ic in manufacturer:
            attrib = ic.attrib
            raw_names = attrib.get("name", "")
            if not raw_names:
                continue
            variants = [v.strip() for v in raw_names.split(",") if v.strip()]

            try:
                pin_count = int(attrib.get("pins", "0"))
            except ValueError:
                pin_count = 0

            entry = _make_entry(
                variants         = variants,
                manufacturer     = mfr_name,
                chip_type        = TYPE_LOGIC,
                code_memory_size = 0,
                data_memory_size = 0,
                pin_count        = pin_count,
                protocol_id      = "",
                chip_id          = "",
                voltages         = attrib.get("voltage", ""),
                flags            = "",
            )
            for variant in variants:
                db[variant] = entry

    return db

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def _build_db() -> dict[str, dict]:
    db: dict[str, dict] = {}

    if INFOIC_XML.exists():
        db.update(_parse_infoic(INFOIC_XML))
    if LOGICIC_XML.exists():
        # logicic entries are type 5; don't overwrite an existing infoic entry
        for name, entry in _parse_logicic(LOGICIC_XML).items():
            if name not in db:
                db[name] = entry

    return db

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_DB: dict[str, dict] | None = None


def get_db() -> dict[str, dict]:
    global _DB
    if _DB is None:
        _DB = _build_db()
    return _DB


def get_device(name: str) -> dict | None:
    return get_db().get(name)


def all_names() -> list[str]:
    return sorted(get_db().keys())




def ddg_url(name: str) -> str:
    return f"https://duckduckgo.com/?q={quote(name + ' datasheet')}"


if __name__ == "__main__":
    db = get_db()
    print(f"Loaded {len(db):,} device entries")
    sample = get_device("AT28C256")
    if sample:
        print(f"AT28C256: type={sample['type']} ({sample['type_label']}), "
              f"size={sample['size_label']}, pins={sample['pin_count']}")
