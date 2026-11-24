"""
tests/test_core.py
~~~~~~~~~~~~~~~~~~
Unit tests for the minipro bridge, logicdb, and the identification engine.

One class per unit under test.  Most are pure unit tests with no system
dependencies; the logicdb class needs minipro's logicic.xml and skips
automatically when it is absent.
"""

from pathlib import Path

import pytest

from minigecko.core.logicdb import find_logic_ic, list_logic_ics, logicic_xml_path
from minigecko.core import minipro
from minigecko.core.minipro import NO_EXIT_STATUS, MiniproResult


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

    def test_failure_without_exit_status_never_reads_as_exit_zero(self):
        r = MiniproResult(ok=False, stderr="minipro timed out after 120 s")
        assert r.returncode == NO_EXIT_STATUS != 0

    def test_failure_keeps_a_real_exit_status(self):
        assert MiniproResult(ok=False, returncode=1).returncode == 1

    def test_missing_binary_has_no_exit_status(self, monkeypatch):
        monkeypatch.setattr(minipro, "_override_binary", "/nonexistent/minipro")
        r = minipro._run_subprocess(["-D"])
        assert r.ok is False
        assert r.returncode == NO_EXIT_STATUS


# ---------------------------------------------------------------------------
# device_db catalogue parsing
# ---------------------------------------------------------------------------

_INFOIC_WITH_BAD_COMMENT = """<?xml version="1.0" encoding="utf-8"?>
<infoic>
  <database type="INFOIC2PLUS">
    <manufacturer name="TEST">
      <!-- T76 only (not used for read/write) -- verify -->
      <ic name="27C256@DIP28" type="1" chip_id="0x8C" flags="0x0"/>
    </manufacturer>
  </database>
</infoic>
"""


class TestDeviceDbParsing:
    def test_double_dash_in_a_comment_does_not_empty_the_catalogue(self, tmp_path):
        # minipro's infoic.xml (commit 80a560b) has "--" inside a comment,
        # which strict XML forbids; minipro's parser tolerates it.
        from minigecko.core.device_db import _parse_infoic

        path = tmp_path / "infoic.xml"
        path.write_text(_INFOIC_WITH_BAD_COMMENT)
        assert "27C256@DIP28" in _parse_infoic(path)

    def _write_sections(self, tmp_path, types=("INFOICT76", "INFOIC2PLUS", "INFOIC")):
        # Same name in every section, with a per-section chip ID, so a test can
        # tell which section an entry came from.
        sections = "".join(
            f'<database type="{t}"><manufacturer name="M">'
            f'<ic name="27C256@DIP28" type="1" chip_id="0x{i + 1:02X}" flags="0x0"/>'
            f"</manufacturer></database>"
            for i, t in enumerate(types)
        )
        path = tmp_path / "infoic.xml"
        path.write_text(f"<infoic>{sections}</infoic>")
        return path

    def test_default_section_is_tl866ii_plus_not_the_first(self, tmp_path):
        from minigecko.core.device_db import _parse_infoic

        db = _parse_infoic(self._write_sections(tmp_path))
        assert db["27C256@DIP28"]["chip_id"] == "0x02"  # INFOIC2PLUS, not INFOICT76

    @pytest.mark.parametrize("section, chip_id", [
        ("INFOICT76", "0x01"), ("INFOIC2PLUS", "0x02"), ("INFOIC", "0x03"),
    ])
    def test_selects_the_named_section(self, tmp_path, section, chip_id):
        from minigecko.core.device_db import _parse_infoic

        db = _parse_infoic(self._write_sections(tmp_path), section)
        assert db["27C256@DIP28"]["chip_id"] == chip_id

    def test_missing_section_falls_back_to_first_with_a_warning(self, tmp_path, caplog):
        from minigecko.core.device_db import _parse_infoic

        db = _parse_infoic(self._write_sections(tmp_path, ("INFOICT76",)), "INFOIC2PLUS")
        assert db["27C256@DIP28"]["chip_id"] == "0x01"
        assert any(r.levelname == "WARNING" for r in caplog.records)

    @pytest.mark.parametrize("hardware, section", [
        ("TL866A", "INFOIC"), ("TL866CS", "INFOIC"), ("T76", "INFOICT76"),
        ("TL866II+", "INFOIC2PLUS"), ("T48", "INFOIC2PLUS"), ("T56", "INFOIC2PLUS"),
        ("", "INFOIC2PLUS"),
    ])
    def test_section_for_programmer_follows_minipro(self, hardware, section):
        # Mirrors translate_db() in minipro's src/database.c.
        from minigecko.core.device_db import section_for_programmer

        assert section_for_programmer(hardware) == section

    def test_use_programmer_reloads_only_on_a_section_change(self, monkeypatch):
        from minigecko.core import device_db

        monkeypatch.setattr(device_db, "_section", "INFOIC2PLUS")
        monkeypatch.setattr(device_db, "_DB", {"cached": {}})

        assert device_db.use_programmer("T48") is False
        assert device_db._DB == {"cached": {}}

        assert device_db.use_programmer("T76") is True
        assert device_db._section == "INFOICT76"
        assert device_db._DB is None

    def test_unparseable_catalogue_is_logged_not_silent(self, tmp_path, caplog):
        from minigecko.core.device_db import _parse_infoic

        path = tmp_path / "infoic.xml"
        path.write_text("<infoic><database>")
        assert _parse_infoic(path) == {}
        assert any(
            r.levelname == "ERROR" and "infoic.xml" in r.getMessage()
            for r in caplog.records
        )


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


from minigecko.core.minipro import parse_bad_pins


class TestParseBadPins:
    _EMPTY_SOCKET = (
        "Found TL866II+ 04.2.132 (0x284)\n"
        "Bad contact on pin:1\n"
        "Bad contact on pin:2\n"
        "Bad contact on pin:27\n"
    )

    def test_extracts_pin_numbers(self):
        assert parse_bad_pins(self._EMPTY_SOCKET) == [1, 2, 27]

    def test_no_bad_pins(self):
        assert parse_bad_pins("Found TL866II+ 04.2.132 (0x284)\n") == []

    def test_ignores_banner_numbers(self):
        assert parse_bad_pins("Found TL866II+ 04.2.132 (0x284)") == []

    def test_deduplicates_and_sorts(self):
        text = "Bad contact on pin:5\nBad contact on pin:2\nBad contact on pin:5\n"
        assert parse_bad_pins(text) == [2, 5]

    def test_empty_text(self):
        assert parse_bad_pins("") == []


from minigecko.core.minipro import blank_check_verdict


class TestWriteDeviceArgs:
    def _args(self, monkeypatch, **kw):
        from minigecko.core import minipro as mp
        seen = {}
        monkeypatch.setattr(mp, "_run", lambda args, **k: seen.setdefault("a", args))
        mp.write_device("AT28C64", Path("x.bin"), **kw)
        return seen["a"]

    def test_verify_is_minipro_default(self, monkeypatch):
        args = self._args(monkeypatch)
        assert "-v" not in args and "-P" not in args

    def test_skip_verify_is_dash_v_never_write_protect(self, monkeypatch):
        args = self._args(monkeypatch, verify=False)
        assert "-v" in args
        assert "-P" not in args  # -P is --protect in minipro


class TestBlankCheckVerdict:
    """Only minipro's own not-blank wording counts as 'not blank'."""

    def test_blank(self):
        verdict, _ = blank_check_verdict(
            MiniproResult(ok=True, stderr="Code memory section is blank.\n"))
        assert verdict == "blank"

    def test_used_memory_chip_names_first_byte(self):
        r = MiniproResult(ok=False, returncode=1, stderr=(
            "Found TL866II+ 04.2.132 (0x284)\n"
            "Verification failed at address 0x01A0: File=0xFF, Device=0x3c\n"))
        assert blank_check_verdict(r) == (
            "not blank", "first used byte at 0x01A0 reads 0x3C")

    def test_used_gal(self):
        r = MiniproResult(ok=False, returncode=1, stderr="This device is not blank.\n")
        assert blank_check_verdict(r)[0] == "not blank"

    def test_empty_socket_is_an_error_not_a_used_chip(self):
        r = MiniproResult(ok=False, returncode=1, stderr=TestParseBadPins._EMPTY_SOCKET)
        assert blank_check_verdict(r) == ("error", "Bad contact on pin:27")

    def test_missing_binary_is_an_error(self):
        r = MiniproResult(ok=False, stderr="minipro not found")
        assert blank_check_verdict(r)[0] == "error"

    def test_silent_failure_is_an_error(self):
        assert blank_check_verdict(MiniproResult(ok=False))[1] == (
            "minipro failed with no message")

    # Recorded on the bench 2026-11-24: empty socket, AT28C64 profile.
    _EMPTY_BLANK = MiniproResult(ok=True, returncode=0, stderr=(
        "Found TL866II+ 04.2.132 (0x284)\nReading Code...  120 ms  OK\n"
        "Code memory section is blank.\n"))
    _EMPTY_CONTACT = MiniproResult(ok=False, returncode=1, stderr=(
        "Found TL866II+ 04.2.132 (0x284)\n"
        + "".join(f"Bad contact on pin:{p}\n" for p in (2, 3, 27, 28))))

    def _fake_minipro(self, monkeypatch, contact, blank):
        from minigecko.core import minipro as mp
        calls = []

        def run(args, **_k):
            calls.append(args)
            return contact if "-z" in args else blank
        monkeypatch.setattr(mp, "_run", run)
        return calls

    def test_empty_socket_is_never_called_blank(self, monkeypatch):
        from minigecko.core.minipro import checked_blank_check
        calls = self._fake_minipro(monkeypatch, self._EMPTY_CONTACT, self._EMPTY_BLANK)
        assert checked_blank_check("AT28C64") == (
            "error", "no contact on pin 2, 3, 27, 28: seat the chip and try again")
        assert not any("-b" in a for a in calls)  # blank check never ran

    def test_good_contact_then_blank(self, monkeypatch):
        from minigecko.core.minipro import checked_blank_check
        good = MiniproResult(ok=True, stderr="Found TL866II+ 04.2.132 (0x284)\n")
        calls = self._fake_minipro(monkeypatch, good, self._EMPTY_BLANK)
        assert checked_blank_check("AT28C64")[0] == "blank"
        assert ["-z" in a for a in calls] == [True, False]

    def test_contact_check_failing_without_pins_is_an_error(self, monkeypatch):
        from minigecko.core.minipro import checked_blank_check
        broken = MiniproResult(ok=False, stderr="No programmer found.\n")
        self._fake_minipro(monkeypatch, broken, self._EMPTY_BLANK)
        assert checked_blank_check("AT28C64") == (
            "error", "contact check failed: No programmer found.")

    def test_emulator_wording_matches(self, monkeypatch):
        from minigecko.core import emulator
        monkeypatch.setattr(emulator, "_fixture_for", lambda d: b"\x00")
        assert blank_check_verdict(emulator._emu_blank_check("AT28C64"))[0] == "not blank"
        monkeypatch.setattr(emulator, "_fixture_for", lambda d: None)
        assert blank_check_verdict(emulator._emu_blank_check("AT28C64"))[0] == "blank"


class TestFeatureLines:
    """The info panel lists only flags that are set, in plain words."""

    def _lines(self, name):
        from minigecko.core import get_device
        from minigecko.ui.panels.ic_info_panel import feature_lines
        return feature_lines(get_device(name))

    def test_chip_id_is_not_listed(self):
        assert not any("ID" in ln for ln in self._lines("W27C512@DIP28"))
        assert self._lines("AT28C64") == ["• Erases electrically"]

    def test_sram_has_nothing_to_say(self):
        assert self._lines("62256") == []

    def test_socket_only_interface_is_not_listed(self):
        assert not any("ZIF" in ln or "ICSP" in ln for ln in self._lines("AT28C64"))

    def test_unknown_chip(self):
        from minigecko.ui.panels.ic_info_panel import feature_lines
        assert feature_lines({}) == []


def test_empty_socket_many_pins_says_seat_a_chip(monkeypatch):
    from minigecko.core import minipro as mp
    many = MiniproResult(ok=False, returncode=1, stderr="".join(
        f"Bad contact on pin:{p}\n" for p in range(2, 27)))
    monkeypatch.setattr(mp, "_run", lambda args, **k: many)
    assert mp.checked_blank_check("AT28C64") == (
        "error", "no contact on 25 pins: is a chip seated?")


JED_DIR = Path(__file__).parent / "data" / "jed"


class TestJedec:
    """JEDEC files are checked against the chip before minipro sees them."""

    def test_reads_fuse_count_device_and_checksum(self):
        from minigecko.core.jedec import parse_jed
        jed = parse_jed((JED_DIR / "counter_16v8.jed").read_text())
        assert (jed.device, jed.fuse_count) == ("GAL16V8", 2194)
        assert jed.declared_checksum == jed.fuse_checksum == 0x3E11

    def test_wincupl_file_checksum_matches(self):
        from minigecko.core.jedec import parse_jed
        jed = parse_jed((JED_DIR / "forbin80_cf_22v10.jed").read_text(errors="replace"))
        assert (jed.device, jed.fuse_count) == ("g22v10", 5892)
        assert jed.declared_checksum == jed.fuse_checksum

    def test_16v8_file_fits_atf16v8b(self):
        from minigecko.core.jedec import check_jed_for_chip
        assert check_jed_for_chip(JED_DIR / "counter_16v8.jed", "ATF16V8B", 2194) is None

    def test_22v10_file_refused_for_16v8(self):
        from minigecko.core.jedec import check_jed_for_chip
        why = check_jed_for_chip(JED_DIR / "forbin80_cf_22v10.jed", "ATF16V8B", 2194)
        assert "5892 fuses" in why and "ATF16V8B has 2194" in why and "g22v10" in why

    def test_damaged_checksum_refused(self):
        from minigecko.core.jedec import check_jed_for_chip
        why = check_jed_for_chip(JED_DIR / "bad_checksum_22v10.jed", "GAL22V10", 5892)
        assert "damaged" in why and "0x4432" in why and "0x4478" in why

    def test_not_a_jed_file(self, tmp_path):
        from minigecko.core.jedec import check_jed_for_chip
        f = tmp_path / "rom.jed"
        f.write_bytes(b"\xff" * 64)
        assert "no fuse count" in check_jed_for_chip(f, "ATF16V8B", 2194)


class TestPldFormat:
    def _capture(self, monkeypatch):
        from minigecko.core import minipro as mp
        calls = []
        monkeypatch.setattr(mp, "_run", lambda args, **k: calls.append(args) or MiniproResult(ok=True))
        return mp, calls

    def test_pld_picks_jed_and_sends_no_format_flag(self, monkeypatch):
        mp, calls = self._capture(monkeypatch)
        assert mp.format_for_device("ATF16V8B") == "JED"
        assert mp.format_for_device("AT28C64") == "BIN"
        assert mp.write_device("ATF16V8B", JED_DIR / "counter_16v8.jed").ok
        assert calls == [["-p", "ATF16V8B", "-w", str(JED_DIR / "counter_16v8.jed"), "-y"]]

    def test_mismatched_jed_never_reaches_minipro(self, monkeypatch):
        mp, calls = self._capture(monkeypatch)
        r = mp.write_device("ATF16V8B", JED_DIR / "forbin80_cf_22v10.jed")
        assert not r.ok and r.data["refused"] and "Refused:" in r.output
        r = mp.verify_device("ATF16V8B", JED_DIR / "forbin80_cf_22v10.jed")
        assert not r.ok and r.data["refused"]
        assert calls == []

    def test_ihex_still_sends_format_flag(self, monkeypatch):
        mp, calls = self._capture(monkeypatch)
        mp.read_device("AT28C64", Path("out.hex"), format="IHEX")
        assert calls[0][-3:] == ["-f", "ihex", "-y"]
