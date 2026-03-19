"""Persistent UI state helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path.home() / ".config" / "minigecko" / "state.json"
_DEFAULT_STATE: dict = {
    "hex_panel_width": 66,
    "info_panel_height": 18,
    "last_directory": str(Path.home()),
    "minipro_path": "",  # empty = find on PATH; set to absolute path to override
}


def _load_state() -> dict:
    try:
        return {**_DEFAULT_STATE, **json.loads(_CONFIG_PATH.read_text())}
    except Exception as exc:
        logger.warning("Failed to load UI state from %s: %s", _CONFIG_PATH, exc)
        return dict(_DEFAULT_STATE)


def _save_state(state: dict) -> None:
    try:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.write_text(json.dumps(state, indent=2))
    except Exception as exc:
        logger.warning("Failed to save UI state to %s: %s", _CONFIG_PATH, exc)
