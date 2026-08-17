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
from minigecko.core.minipro import MiniproResult, ProgrammerInfo


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

    def test_every_indexed_name_is_id_capable(self):
        index = chip_id_index()
        sample = [n for names in list(index.values())[:20] for n in names][:50]
        from minigecko.core.device_db import get_device
        for name in sample:
            entry = get_device(name)
            assert entry is not None
            assert is_id_capable(entry)


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


class TestSuggestedNextSteps:
    def test_logic_candidates_suggest_the_sweep(self):
        steps = suggested_next_steps(tier0_candidates(ChipHint(pin_count=14)))
        assert any(step.stage == 2 for step in steps)

    def test_steps_carry_estimates(self):
        steps = suggested_next_steps(tier0_candidates(ChipHint(pin_count=14)))
        assert all(step.estimate for step in steps)

    def test_no_candidates_means_no_steps(self):
        assert suggested_next_steps([]) == []
