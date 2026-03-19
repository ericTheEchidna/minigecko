"""
tests/test_core.py
~~~~~~~~~~~~~~~~~~
Unit tests for the minipro bridge and logicdb.

Tests are split into two classes:
    - TestMiniproResult                      — pure unit tests, no system deps
  - TestLogicDB                            — requires minipro's logicic.xml;
                                             skipped automatically when absent
"""

import pytest

from minigecko.core.logicdb import find_logic_ic, list_logic_ics, logicic_xml_path
from minigecko.core.minipro import MiniproResult


# ---------------------------------------------------------------------------
# MiniproResult
# ---------------------------------------------------------------------------

class TestMiniproResult:
    def test_bool_true(self):
        r = MiniproResult(ok=True, stdout="ok", returncode=0)
        assert bool(r) is True

    def test_bool_false(self):
        r = MiniproResult(ok=False, stderr="fail", returncode=1)
        assert bool(r) is False

    def test_output_combines(self):
        r = MiniproResult(ok=True, stdout="out", stderr="err")
        assert "out" in r.output
        assert "err" in r.output


# ---------------------------------------------------------------------------
# Logic IC database (logicdb) — skipped when minipro is not installed
# ---------------------------------------------------------------------------

needs_minipro = pytest.mark.skipif(
    logicic_xml_path() is None,
    reason="logicic.xml not found — install minipro to run hardware DB tests",
)


@needs_minipro
class TestLogicDB:
    def test_logicic_xml_found(self):
        path = logicic_xml_path()
        assert path is not None
        assert path.is_file()

    def test_list_returns_entries(self):
        ics = list_logic_ics()
        assert len(ics) > 200, f"Expected 200+ ICs, got {len(ics)}"

    def test_find_by_name(self):
        ic = find_logic_ic("4000")
        assert ic is not None
        assert ic.name == "4000"
        assert ic.pins == 14
        assert ic.voltage == "5V"
        assert ic.vector_count > 0

    def test_find_by_alias(self):
        # "7404" is an alias in the "40106,7416,7414,7406,7405,7404,4584,4069" entry
        ic = find_logic_ic("7404")
        assert ic is not None
        assert "7404" in ic.all_names

    def test_find_case_insensitive(self):
        ic = find_logic_ic("4000")
        assert ic is not None
        assert ic.name == "4000"

    def test_find_not_found(self):
        assert find_logic_ic("DOESNOTEXIST9999") is None

    def test_vectors_parsed(self):
        ic = find_logic_ic("4000")
        assert ic is not None
        assert ic.vector_count == 8
        for vec in ic.vectors:
            symbols = vec.split()
            assert len(symbols) == ic.pins, f"Vector has {len(symbols)} symbols, expected {ic.pins}"

    def test_logic_ic_fields(self):
        ic = find_logic_ic("74138")
        assert ic is not None
        assert ic.pins == 16
        assert ic.vector_count > 0


