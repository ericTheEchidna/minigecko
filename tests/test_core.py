"""
tests/test_core.py
~~~~~~~~~~~~~~~~~~
Unit tests for the minipro bridge, logicdb, and the identification engine.

One class per unit under test.  Most are pure unit tests with no system
dependencies; the logicdb class needs minipro's logicic.xml and skips
automatically when it is absent.
"""

import importlib

import pytest

from minigecko.core.identify import (
    CONFIDENCE_ORDER,
    DEFAULT_SOCKET_WIDTH,
    DIP_FAMILIES,
    EVIDENCE_MARKING,
    EVIDENCE_PACKAGE,
    EVIDENCE_SILICON_ID,
    MUTE_IDS,
    Candidate,
    ChipHint,
    Evidence,
    IdentifyReport,
    NextStep,
    chip_id_index,
    default_probe,
    id_read_voltage_note,
    identify,
    is_id_capable,
    marking_matches,
    normalize_chip_id,
    package_family,
    parse_package,
    probe_carriers,
    socket_pins,
    socket_width,
    suggested_next_steps,
    tier0_candidates,
    unique_entries,
)
from minigecko.core.logicdb import find_logic_ic, list_logic_ics, logicic_xml_path
from minigecko.core import minipro
from minigecko.core.minipro import NO_EXIT_STATUS, MiniproResult, ProgrammerInfo


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

    def test_missing_binary_is_not_a_chip_id_match(self, monkeypatch):
        monkeypatch.setattr(minipro, "_transport", minipro._run_subprocess)
        monkeypatch.setattr(minipro, "_override_binary", "/nonexistent/minipro")
        assert minipro.read_chip_id("AM2764A@DIP28").data["matched"] is False


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
        monkeypatch.setattr(device_db, "_reload_hooks", [])
        calls = []
        device_db.on_reload(lambda: calls.append(1))

        assert device_db.use_programmer("T48") is False
        assert device_db._DB == {"cached": {}} and calls == []

        assert device_db.use_programmer("T76") is True
        assert device_db._section == "INFOICT76"
        assert device_db._DB is None and calls == [1]

    def test_identify_caches_clear_on_reload(self, monkeypatch):
        from minigecko.core import device_db

        unique_entries.cache_clear()
        unique_entries()
        assert unique_entries.cache_info().currsize == 1
        monkeypatch.setattr(device_db, "_section", "INFOIC2PLUS")
        monkeypatch.setattr(device_db, "_DB", device_db._DB)
        device_db.use_programmer("T76")
        assert unique_entries.cache_info().currsize == 0
        assert chip_id_index.cache_info().currsize == 0
        device_db.use_programmer("TL866II+")

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


# ---------------------------------------------------------------------------
# Package parsing and socket pin resolution (identify)
# ---------------------------------------------------------------------------

class TestPackageParsing:
    def test_plain_dip(self):
        assert parse_package("DIP28") == ("DIP", 28)

    def test_suffix_in_parens_is_ignored(self):
        assert parse_package("TSOP32(ADP:Pin9to1)") == ("TSOP", 32)

    def test_recommend_suffix_is_ignored(self):
        assert parse_package("BGA100(recommend)") == ("BGA", 100)

    def test_empty_package(self):
        assert parse_package("") == (None, None)

    def test_family_without_digits(self):
        # "OC" appears as a package on two logic entries and carries no pin count
        assert parse_package("OC") == (None, None)

    def test_lowercase_family_is_normalised(self):
        assert parse_package("dip8") == ("DIP", 8)

    def test_dip_families_contains_dip(self):
        assert "DIP" in DIP_FAMILIES


class TestSocketPins:
    def test_package_string_wins(self):
        # pin_count is scrambled for BGA parts: 33 really means BGA48.
        entry = {"package": "BGA48", "pin_count": 33}
        assert socket_pins(entry) == 48

    def test_plcc_package_string_wins(self):
        entry = {"package": "PLCC32", "pin_count": 63}
        assert socket_pins(entry) == 32

    def test_falls_back_to_pin_count_when_package_empty(self):
        # Logic IC entries from logicic.xml: empty package, reliable pin_count.
        entry = {"package": "", "pin_count": 14}
        assert socket_pins(entry) == 14

    def test_returns_none_when_both_unusable(self):
        assert socket_pins({"package": "", "pin_count": 0}) is None

    def test_rejects_odd_pin_count_fallback(self):
        # DIP pin counts are always even; an odd value is not a pin count.
        assert socket_pins({"package": "", "pin_count": 33}) is None

    def test_rejects_out_of_range_pin_count_fallback(self):
        assert socket_pins({"package": "", "pin_count": 200}) is None

    def test_package_family_empty_is_none(self):
        assert package_family({"package": ""}) is None

    def test_package_family_reads_package(self):
        assert package_family({"package": "SOIC8"}) == "SOIC"


# ---------------------------------------------------------------------------
# Marking fragment matcher (identify)
# ---------------------------------------------------------------------------

class TestMarkingMatcher:
    def test_bare_fragment_is_substring(self):
        assert marking_matches("74LS", ["SN74LS00"]) is True

    def test_bare_fragment_no_match(self):
        assert marking_matches("74LS", ["AM2764A"]) is False

    def test_case_insensitive(self):
        assert marking_matches("74ls", ["SN74LS00"]) is True

    def test_question_mark_matches_one_char(self):
        assert marking_matches("74??00", ["74LS00"]) is True

    def test_question_mark_requires_exact_length(self):
        assert marking_matches("74?00", ["74LS00"]) is False

    def test_star_matches_run(self):
        assert marking_matches("27*256", ["27C256"]) is True

    def test_wildcard_matches_within_a_prefixed_name(self):
        assert marking_matches("74??00", ["SN74LS00"]) is True

    def test_wildcard_matches_within_a_suffixed_name(self):
        assert marking_matches("27*256", ["AM27C256@DIP28"]) is True

    def test_matches_any_of_several_names(self):
        assert marking_matches("2764", ["AM2764A", "MBM2764"]) is True

    def test_empty_marking_matches_everything(self):
        assert marking_matches("", ["ANYTHING"]) is True

    def test_whitespace_only_marking_matches_everything(self):
        assert marking_matches("   ", ["ANYTHING"]) is True

    def test_no_names_never_matches(self):
        assert marking_matches("74LS", []) is False


# ---------------------------------------------------------------------------
# Chip ID index and probe carriers
# ---------------------------------------------------------------------------

class TestChipIdNormalisation:
    def test_strips_prefix_and_upper_cases(self):
        assert normalize_chip_id("0x01007e22") == "1007E22"

    def test_strips_leading_zeros(self):
        assert normalize_chip_id("0x0108") == "108"

    def test_bare_hex_without_prefix(self):
        assert normalize_chip_id("108") == "108"

    def test_all_zero_normalises_to_zero(self):
        assert normalize_chip_id("0x00000000") == "0"

    def test_whitespace_tolerated(self):
        assert normalize_chip_id("  0X1C2013  ") == "1C2013"

    def test_empty_string(self):
        assert normalize_chip_id("") == ""

    def test_widths_agree_after_normalising(self):
        assert normalize_chip_id("0x0108") == normalize_chip_id("0x00000108")


class TestChipIdIndex:
    def test_index_is_not_empty(self):
        assert len(chip_id_index()) > 100

    def test_known_collision_is_a_group(self):
        # 0x01007e22 is shared by 136 devices in minipro's catalogue.
        names = chip_id_index()[normalize_chip_id("0x01007e22")]
        assert len(names) > 50

    def test_all_zero_id_absent(self):
        assert normalize_chip_id("0x00000000") not in chip_id_index()

    def test_index_is_cached(self):
        assert chip_id_index() is chip_id_index()

    def test_index_is_read_only(self):
        with pytest.raises(TypeError):
            chip_id_index()["ZZZZ"] = ("nope",)

    def test_indexed_names_are_id_capable_except_known_shadowed(self):
        # device_db name keys are not unique, so a handful of indexed names
        # resolve to a non-ID-capable entry (MINIGECKO-008).  Closing that
        # should empty this set and turn this test red, which is the point:
        # it is the regression net for the fix.
        KNOWN_SHADOWED = {"27C256@DIP28", "27C256@PLCC32"}

        from minigecko.core.device_db import get_device

        shadowed = set()
        for names in chip_id_index().values():
            for name in names:
                entry = get_device(name)
                assert entry is not None
                if not is_id_capable(entry):
                    shadowed.add(name)

        assert shadowed == KNOWN_SHADOWED


class TestUniqueEntries:
    def test_fewer_than_name_keys(self):
        from minigecko.core.device_db import get_db
        assert len(unique_entries()) < len(get_db())

    def test_no_duplicate_objects(self):
        entries = unique_entries()
        assert len({id(e) for e in entries}) == len(entries)


class TestProbeCarriers:
    def test_returns_carriers_for_dip28(self):
        assert probe_carriers(28)

    @pytest.mark.parametrize("pins", [28, 32, 40])
    def test_first_carrier_at_memory_widths_reads_id_the_eprom_way(self, pins):
        # Bench 2026-11-23 (MINIGECKO-00B): the 27-series ID read raises A9 to
        # ~12 V.  That is kept on purpose; the warning must say so.
        note = id_read_voltage_note(probe_carriers(pins)[0])
        assert "A9" in note and "12 V" in note
        assert "SRAM" in note

    def test_other_carriers_warn_without_claiming_a9(self):
        note = id_read_voltage_note(probe_carriers(14)[0])  # an AVR
        assert "A9" not in note
        assert "above VCC" in note and "SRAM" in note

    def test_carriers_match_pin_count_exactly(self):
        from minigecko.core.device_db import get_device
        for name in probe_carriers(28)[:20]:
            assert socket_pins(get_device(name)) == 28

    def test_carriers_are_dip(self):
        from minigecko.core.device_db import get_device
        for name in probe_carriers(28)[:20]:
            assert package_family(get_device(name)) in DIP_FAMILIES

    def test_carriers_are_id_capable(self):
        from minigecko.core.device_db import get_device
        for name in probe_carriers(28)[:20]:
            assert is_id_capable(get_device(name))

    def test_no_carriers_for_impossible_pin_count(self):
        assert probe_carriers(3) == []

    def test_carrier_names_agree_with_the_requested_package(self):
        from minigecko.core.identify import parse_package
        for name in probe_carriers(28):
            family, pins = parse_package(name.split("@", 1)[1]) if "@" in name else (None, None)
            assert family in DIP_FAMILIES, name
            assert pins == 28, name

    def test_carrier_names_resolve_to_eligible_entries(self):
        from minigecko.core.device_db import get_device
        for name in probe_carriers(28)[:40]:
            entry = get_device(name)
            assert entry is not None, name
            assert is_id_capable(entry), name
            assert socket_pins(entry) == 28, name


class TestChipHint:
    def test_defaults(self):
        hint = ChipHint(pin_count=28)
        assert hint.via_adapter is False
        assert hint.marking is None

    def test_accepts_marking_and_adapter(self):
        hint = ChipHint(pin_count=8, via_adapter=True, marking="25Q")
        assert hint.marking == "25Q"
        assert hint.via_adapter is True


class TestConfidence:
    def _cand(self, *kinds):
        return Candidate(
            name="X",
            entry={},
            evidence=[Evidence(kind=k, detail="d") for k in kinds],
        )

    def test_silicon_id_is_confirmed(self):
        assert self._cand(EVIDENCE_SILICON_ID, EVIDENCE_PACKAGE).confidence == "confirmed"

    def test_silicon_id_wins_over_marking(self):
        cand = self._cand(EVIDENCE_SILICON_ID, EVIDENCE_MARKING)
        assert cand.confidence == "confirmed"

    def test_marking_without_silicon_is_probable(self):
        assert self._cand(EVIDENCE_MARKING, EVIDENCE_PACKAGE).confidence == "probable"

    def test_package_only_is_possible(self):
        assert self._cand(EVIDENCE_PACKAGE).confidence == "possible"

    def test_no_evidence_is_possible(self):
        assert self._cand().confidence == "possible"

    def test_confidence_order_ranks_confirmed_first(self):
        assert CONFIDENCE_ORDER["confirmed"] < CONFIDENCE_ORDER["probable"]
        assert CONFIDENCE_ORDER["probable"] < CONFIDENCE_ORDER["possible"]

    def test_sort_key_orders_confirmed_before_possible(self):
        confirmed = self._cand(EVIDENCE_SILICON_ID)
        possible = self._cand(EVIDENCE_PACKAGE)
        assert sorted([possible, confirmed], key=lambda c: c.sort_key)[0] is confirmed


class TestReportModel:
    def test_empty_report_defaults(self):
        report = IdentifyReport(candidates=[], diagnostics=[], suggested_next=[])
        assert report.observed_id is None
        assert report.carrier is None

    def test_next_step_defaults_to_unavailable(self):
        step = NextStep(label="Logic sweep", estimate="~90 s", stage=2)
        assert step.available is False


class TestTier0:
    def test_returns_candidates_for_dip28(self):
        assert tier0_candidates(ChipHint(pin_count=28))

    def test_all_candidates_match_pin_count(self):
        for cand in tier0_candidates(ChipHint(pin_count=28)):
            assert socket_pins(cand.entry) == 28

    def test_direct_mode_excludes_non_dip_packages(self):
        for cand in tier0_candidates(ChipHint(pin_count=8)):
            family = package_family(cand.entry)
            assert family is None or family in DIP_FAMILIES

    def test_adapter_mode_widens_the_pool(self):
        direct = tier0_candidates(ChipHint(pin_count=8))
        adapter = tier0_candidates(ChipHint(pin_count=8, via_adapter=True))
        assert len(adapter) > len(direct)

    def test_adapter_mode_includes_non_dip(self):
        families = {
            package_family(c.entry)
            for c in tier0_candidates(ChipHint(pin_count=8, via_adapter=True))
        }
        assert families - DIP_FAMILIES - {None}

    def test_unknown_package_entries_survive_direct_mode(self):
        # Logic ICs have empty package strings; they must not be filtered out.
        names = {c.name for c in tier0_candidates(ChipHint(pin_count=14))}
        assert "4001" in names

    def test_unknown_package_entries_survive_adapter_mode(self):
        names = {c.name for c in tier0_candidates(ChipHint(pin_count=14, via_adapter=True))}
        assert "4001" in names

    def test_marking_narrows_results(self):
        wide = tier0_candidates(ChipHint(pin_count=28))
        narrow = tier0_candidates(ChipHint(pin_count=28, marking="2764"))
        assert 0 < len(narrow) < len(wide)

    def test_marking_candidates_carry_marking_evidence(self):
        cands = tier0_candidates(ChipHint(pin_count=28, marking="2764"))
        assert cands
        for cand in cands:
            kinds = {e.kind for e in cand.evidence}
            assert EVIDENCE_MARKING in kinds

    def test_no_marking_yields_package_evidence_only(self):
        for cand in tier0_candidates(ChipHint(pin_count=28))[:20]:
            assert {e.kind for e in cand.evidence} == {EVIDENCE_PACKAGE}

    def test_impossible_pin_count_returns_empty(self):
        assert tier0_candidates(ChipHint(pin_count=3)) == []

    def test_unmatchable_marking_returns_empty(self):
        assert tier0_candidates(ChipHint(pin_count=28, marking="ZZZQQQ")) == []

    def test_results_are_sorted_by_confidence_then_name(self):
        cands = tier0_candidates(ChipHint(pin_count=28))
        assert [c.sort_key for c in cands] == sorted(c.sort_key for c in cands)

    def test_candidate_names_resolve_to_their_own_entry(self):
        from minigecko.core.device_db import get_device
        for cand in tier0_candidates(ChipHint(pin_count=28))[:60]:
            assert get_device(cand.name) is cand.entry, cand.name


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


class TestReadChipId:
    def _with_transport(self, monkeypatch, result):
        from minigecko.core import minipro as mp
        monkeypatch.setattr(mp, "_run", lambda *a, **k: result)
        return mp

    def test_parses_mismatch_despite_nonzero_exit(self, monkeypatch):
        from minigecko.core.minipro import MiniproResult
        raw = MiniproResult(
            ok=False,
            returncode=1,
            stderr=(
                "Found TL866II+ 04.2.132 (0x284)\n\n"
                "Chip ID mismatch: expected 0x0108, got 0xFFFF (unknown)\n"
            ),
        )
        mp = self._with_transport(monkeypatch, raw)
        result = mp.read_chip_id("AM2764A@DIP28")
        assert result.data["chip_id"] == "0XFFFF"
        assert result.data["expected_id"] == "0X0108"
        assert result.data["matched"] is False

    def test_lowercase_hex_is_upper_cased(self, monkeypatch):
        from minigecko.core.minipro import MiniproResult
        raw = MiniproResult(
            ok=False,
            returncode=1,
            stderr="Chip ID mismatch: expected 0x01007e22, got 0x1c2013 (unknown)\n",
        )
        mp = self._with_transport(monkeypatch, raw)
        assert mp.read_chip_id("X").data["chip_id"] == "0X1C2013"

    def test_matched_case_when_exit_zero_and_no_mismatch_line(self, monkeypatch):
        from minigecko.core.minipro import MiniproResult
        raw = MiniproResult(ok=True, returncode=0, stderr="Found TL866II+ 04.2.132\n")
        mp = self._with_transport(monkeypatch, raw)
        data = mp.read_chip_id("X").data
        assert data["matched"] is True
        assert data["chip_id"] is None

    def test_unparseable_failure_reports_neither(self, monkeypatch):
        from minigecko.core.minipro import MiniproResult
        raw = MiniproResult(ok=False, returncode=1, stderr="usb error\n")
        mp = self._with_transport(monkeypatch, raw)
        data = mp.read_chip_id("X").data
        assert data["matched"] is False
        assert data["chip_id"] is None

    def test_transport_failure_is_not_a_match(self, monkeypatch):
        from minigecko.core.minipro import MiniproResult
        raw = MiniproResult(ok=False, stderr="minipro not found. Install it from ...")
        mp = self._with_transport(monkeypatch, raw)
        data = mp.read_chip_id("X").data
        assert data["matched"] is False
        assert data["chip_id"] is None

    def test_read_chip_id_invokes_only_the_read_id_verb(self, monkeypatch):
        from minigecko.core import minipro as mp
        from minigecko.core.minipro import MiniproResult
        seen = []
        monkeypatch.setattr(
            mp, "_run",
            lambda args, *a, **k: seen.append(args) or MiniproResult(ok=True, returncode=0),
        )
        mp.read_chip_id("AM2764A@DIP28")
        assert seen == [["-p", "AM2764A@DIP28", "-D"]]


# ---------------------------------------------------------------------------
# Socket width
# ---------------------------------------------------------------------------

class TestSocketWidth:
    def test_tl866ii_plus_is_40(self):
        assert socket_width(ProgrammerInfo(connected=True, hardware="TL866II+")) == 40

    def test_t48_is_40(self):
        assert socket_width(ProgrammerInfo(connected=True, hardware="T48")) == 40

    def test_t56_is_48(self):
        assert socket_width(ProgrammerInfo(connected=True, hardware="T56")) == 48

    def test_unknown_model_falls_back(self):
        got = socket_width(ProgrammerInfo(connected=True, hardware="MysteryBox9000"))
        assert got == DEFAULT_SOCKET_WIDTH

    def test_not_connected_falls_back(self):
        assert socket_width(ProgrammerInfo(connected=False)) == DEFAULT_SOCKET_WIDTH

    def test_default_is_40(self):
        assert DEFAULT_SOCKET_WIDTH == 40

    def test_no_info_detects_the_programmer(self, monkeypatch):
        # Imported by name: minigecko.core re-exports identify(), so the
        # function shadows the submodule attribute.
        ident = importlib.import_module("minigecko.core.identify")
        monkeypatch.setattr(
            ident, "detect_programmer",
            lambda: ProgrammerInfo(connected=True, hardware="T56"),
        )
        assert socket_width() == 48


# ---------------------------------------------------------------------------
# identify() orchestrator
# ---------------------------------------------------------------------------

class TestIdentifyTier0Only:
    def test_no_probe_means_no_hardware(self):
        report = identify(ChipHint(pin_count=28))
        assert report.candidates
        assert report.observed_id is None
        assert report.carrier is None

    def test_diagnostic_explains_tier0_only(self):
        report = identify(ChipHint(pin_count=28))
        assert any("no probe" in d.lower() for d in report.diagnostics)

    def test_empty_result_is_diagnosed_not_raised(self):
        report = identify(ChipHint(pin_count=28, marking="ZZZQQQ"))
        assert report.candidates == []
        assert any("no candidate" in d.lower() for d in report.diagnostics)

    def test_suggests_next_steps(self):
        report = identify(ChipHint(pin_count=14))
        assert report.suggested_next
        assert all(step.available is False for step in report.suggested_next)


class TestIdentifyTier1:
    # 0x00000110 is carried by 6 catalogue devices, 3 of them DIP-28
    # (AM27C256@DIP28, AM27H256@DIP28, 27CX256@DIP28) — a real shared-ID group
    # that actually intersects a 28-pin hint.  Verified against the live DB.
    _SHARED_ID = "0x00000110"

    def _shared_id_probe(self, carrier):
        return {
            "chip_id": self._SHARED_ID,
            "expected_id": "0x0108",
            "matched": False,
        }

    def test_probe_narrows_to_the_id_group(self):
        report = identify(ChipHint(pin_count=28), probe=self._shared_id_probe)
        assert report.observed_id == self._SHARED_ID
        assert report.carrier is not None
        assert report.candidates
        assert all(c.confidence == "confirmed" for c in report.candidates)

    def test_probe_result_is_intersected_with_tier0(self):
        tier0 = {c.name for c in tier0_candidates(ChipHint(pin_count=28))}
        report = identify(ChipHint(pin_count=28), probe=self._shared_id_probe)
        assert {c.name for c in report.candidates} <= tier0
        # The group collapses: 6 devices carry the ID, only the 28-pin ones survive.
        assert 0 < len(report.candidates) < 6

    def test_mute_id_is_diagnostic_not_a_match(self):
        probe = lambda carrier: {
            "chip_id": "0xFFFF",
            "expected_id": "0x0108",
            "matched": False,
        }
        report = identify(ChipHint(pin_count=28), probe=probe)
        assert any(
            "mute" in d.lower() or "inserted" in d.lower() for d in report.diagnostics
        )
        assert all(c.confidence != "confirmed" for c in report.candidates)

    def test_all_zero_id_is_mute(self):
        assert normalize_chip_id("0x0000") in MUTE_IDS

    def test_unknown_id_reports_raw_value(self):
        probe = lambda carrier: {
            "chip_id": "0xDEADBE",
            "expected_id": "0x0108",
            "matched": False,
        }
        report = identify(ChipHint(pin_count=28), probe=probe)
        assert any("0xDEADBE" in d for d in report.diagnostics)
        # Falls back to the tier 0 shortlist rather than returning nothing.
        assert report.candidates

    def test_matched_probe_confirms_the_carrier(self):
        probe = lambda carrier: {"chip_id": None, "expected_id": None, "matched": True}
        report = identify(ChipHint(pin_count=28), probe=probe)
        assert report.carrier is not None
        assert any(c.name == report.carrier for c in report.candidates)
        carrier_cand = next(c for c in report.candidates if c.name == report.carrier)
        assert carrier_cand.confidence == "confirmed"

    def test_matched_evidence_does_not_claim_a_read(self):
        # A matched -D returns no ID string of its own, so the reported value is
        # the carrier's catalogue ID and must not be worded as an observation.
        probe = lambda carrier: {"chip_id": None, "expected_id": None, "matched": True}
        report = identify(ChipHint(pin_count=28), probe=probe)
        carrier_cand = next(c for c in report.candidates if c.name == report.carrier)
        summary = carrier_cand.evidence_summary
        assert "read via" not in summary
        assert "silicon ID" not in summary
        assert "catalogue ID" in summary

    def test_mismatch_evidence_does_claim_a_read(self):
        report = identify(ChipHint(pin_count=28), probe=self._shared_id_probe)
        summary = report.candidates[0].evidence_summary
        assert f"silicon ID {self._SHARED_ID} (read via " in summary

    def test_marking_is_blamed_before_the_pin_count(self):
        # The ID group is real and 28-pin, but the marking fragment excludes it,
        # so the pin count is not the thing to doubt.
        report = identify(
            ChipHint(pin_count=28, marking="AM2764"), probe=self._shared_id_probe
        )
        assert any("marking" in d.lower() for d in report.diagnostics)
        assert not any("pin count may be wrong" in d for d in report.diagnostics)

    def test_matched_carrier_excluded_by_marking_is_still_reported(self):
        probe = lambda carrier: {"chip_id": None, "expected_id": None, "matched": True}
        report = identify(ChipHint(pin_count=28, marking="AM2764"), probe=probe)
        assert report.carrier is not None
        # the user must still learn what the socketed chip is
        assert any(report.carrier in d for d in report.diagnostics)

    def test_probe_exception_is_diagnosed_not_raised(self):
        def boom(carrier):
            raise OSError("usb went away")

        report = identify(ChipHint(pin_count=28), probe=boom)
        assert any("usb went away" in d for d in report.diagnostics)
        assert report.candidates  # tier 0 survives

    def test_no_carrier_available_is_diagnosed(self):
        called = []
        probe = lambda carrier: called.append(carrier) or {}
        # 16-pin DIP has 131 catalogue candidates but ZERO ID-capable carriers,
        # so there is nothing to probe with.  Verified against the live DB — do
        # not use 14 here, which has 9 carriers.
        report = identify(ChipHint(pin_count=16), probe=probe)
        assert called == []
        assert report.candidates  # tier 0 still produced a shortlist
        assert any("carrier" in d.lower() for d in report.diagnostics)

    def test_no_probe_does_not_call_the_hardware_path(self, monkeypatch):
        from minigecko.core import minipro as mp
        monkeypatch.setattr(
            mp, "_run",
            lambda *a, **k: pytest.fail("identify() reached minipro without a probe"),
        )
        assert identify(ChipHint(pin_count=28)).candidates


class TestDefaultProbe:
    def _with_read_chip_id(self, monkeypatch, result):
        ident = importlib.import_module("minigecko.core.identify")
        seen = []
        monkeypatch.setattr(
            ident, "read_chip_id",
            lambda device: seen.append(device) or result,
        )
        return seen

    def test_returns_the_data_dict_verbatim(self, monkeypatch):
        data = {"chip_id": "0X1C2013", "expected_id": "0X01007E22", "matched": False}
        seen = self._with_read_chip_id(
            monkeypatch, MiniproResult(ok=False, returncode=1, data=data)
        )
        assert default_probe("AM2764A@DIP28") == data
        assert seen == ["AM2764A@DIP28"]

    def test_failed_transport_data_is_still_returned(self, monkeypatch):
        # ok is False and returncode nonzero on every mismatch, which is this
        # path's success case: default_probe must not gate on either.
        data = {"chip_id": None, "expected_id": None, "matched": False}
        self._with_read_chip_id(
            monkeypatch, MiniproResult(ok=False, returncode=1, data=data)
        )
        assert default_probe("X") == data

    def test_absent_data_becomes_empty_dict(self, monkeypatch):
        self._with_read_chip_id(monkeypatch, MiniproResult(ok=False))
        assert default_probe("X") == {}


class TestSuggestedNextSteps:
    def test_logic_candidates_suggest_the_sweep(self):
        steps = suggested_next_steps(tier0_candidates(ChipHint(pin_count=14)))
        assert any(step.stage == 2 for step in steps)

    def test_steps_carry_estimates(self):
        steps = suggested_next_steps(tier0_candidates(ChipHint(pin_count=14)))
        assert all(step.estimate for step in steps)

    def test_no_candidates_means_no_steps(self):
        assert suggested_next_steps([]) == []
