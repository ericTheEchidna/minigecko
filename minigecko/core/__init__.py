"""
minigecko.core
~~~~~~~~~~
Hardware abstraction layer.  Import from here, not from submodules.

Note: the re-exported ``identify`` function shadows the ``identify`` submodule
attribute, so ``from minigecko.core import identify`` binds the function; use
``from minigecko.core.identify import ...`` to reach the submodule.
"""

from .device_db import (
    TYPE_EEPROM, TYPE_MCU, TYPE_PLD, TYPE_SRAM, TYPE_LOGIC, TYPE_NAND, TYPE_EMMC, TYPE_VGA,
    all_names, ddg_url, decode_flags, get_db, get_description, get_device,
)
from .identify import (
    Candidate,
    ChipHint,
    Evidence,
    IdentifyReport,
    MUTE_IDS,
    NextStep,
    default_probe,
    identify,
    socket_width,
    suggested_next_steps,
)
from .minipro import (
    ChipDevice,
    MiniproResult,
    ProgrammerInfo,
    blank_check_device,
    blank_check_verdict,
    detect_programmer,
    erase_device,
    get_device_info,
    is_available,
    is_emulated,
    list_devices,
    logic_test,
    parse_bad_pins,
    pin_check_device,
    read_chip_id,
    read_device,
    read_pin,
    set_binary_path,
    verify_device,
    write_device,
    write_pins,
)

__all__ = [
    "Candidate",
    "ChipDevice",
    "ChipHint",
    "Evidence",
    "IdentifyReport",
    "MUTE_IDS",
    "MiniproResult",
    "NextStep",
    "ProgrammerInfo",
    "TYPE_EEPROM", "TYPE_MCU", "TYPE_PLD", "TYPE_SRAM",
    "TYPE_LOGIC", "TYPE_NAND", "TYPE_EMMC", "TYPE_VGA",
    "all_names",
    "blank_check_device",
    "blank_check_verdict",
    "ddg_url",
    "decode_flags",
    "default_probe",
    "detect_programmer",
    "erase_device",
    "get_db",
    "get_description",
    "get_device",
    "get_device_info",
    "identify",
    "is_available",
    "list_devices",
    "logic_test",
    "parse_bad_pins",
    "pin_check_device",
    "read_chip_id",
    "read_device",
    "read_pin",
    "set_binary_path",
    "socket_width",
    "suggested_next_steps",
    "verify_device",
    "write_device",
    "write_pins",
]
