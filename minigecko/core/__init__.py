"""
minigecko.core
~~~~~~~~~~
Hardware abstraction layer.  Import from here, not from submodules.
"""

from .device_db import (
    TYPE_EEPROM, TYPE_MCU, TYPE_PLD, TYPE_SRAM, TYPE_LOGIC, TYPE_NAND, TYPE_EMMC, TYPE_VGA,
    all_names, ddg_url, decode_flags, get_db, get_description, get_device,
)
from .minipro import (
    ChipDevice,
    MiniproResult,
    ProgrammerInfo,
    blank_check_device,
    detect_programmer,
    erase_device,
    get_device_info,
    is_available,
    is_emulated,
    list_devices,
    logic_test,
    pin_check_device,
    read_device,
    read_pin,
    set_binary_path,
    verify_device,
    write_device,
    write_pins,
)

__all__ = [
    "ChipDevice",
    "MiniproResult",
    "ProgrammerInfo",
    "TYPE_EEPROM", "TYPE_MCU", "TYPE_PLD", "TYPE_SRAM",
    "TYPE_LOGIC", "TYPE_NAND", "TYPE_EMMC", "TYPE_VGA",
    "all_names",
    "blank_check_device",
    "ddg_url",
    "decode_flags",
    "detect_programmer",
    "erase_device",
    "get_db",
    "get_description",
    "get_device",
    "get_device_info",
    "is_available",
    "list_devices",
    "logic_test",
    "pin_check_device",
    "read_device",
    "read_pin",
    "set_binary_path",
    "verify_device",
    "write_device",
    "write_pins",
]
