# Chip Identifier Stage 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Identify a DIP IC whose top markings are unreadable, non-destructively, by filtering minipro's device catalogue on pin count plus optional marking fragment and then reading the chip's silicon ID with a single read-only probe.

**Architecture:** A pure, hardware-free engine in `minigecko/core/identify.py` builds a reverse index from minipro's `chip_id` values (observed ID → candidate devices) and filters the catalogue by resolved socket pin count. Hardware access is injected as a callable, so the engine cannot touch the programmer unless a probe is explicitly handed in. A three-step `ModalScreen` wizard in `minigecko/ui/modals/identify.py` collects the hint, states the safety implications, and presents ranked candidates with the evidence for each.

**Tech Stack:** Python 3.11+, Textual (TUI framework — the terminal widget/screen library this app is built on), pytest, minipro 0.7.4 CLI.

**Spec:**
- MEMEX vault note `projects/minigecko/chip-identifier-design-faint-marking-ic-identification.md` — "Chip Identifier design (faint-marking IC identification)"
- MEMEX vault note `projects/minigecko/chip-identifier-hardware-verified-minipro-behaviour.md` — "Chip Identifier hardware-verified minipro behaviour"
- MEMEX task **MINIGECKO-005**

The vault lives on the `miso` host, not locally. Read the notes via the
`memex-api` MCP server (`memex_knowledge_read` / `memex_knowledge_search`) or
`http://miso:8002`. This plan restates every fact you need, so it is executable
without them, but the hardware-verified note is worth reading before Task 6.

## Global Constraints

- Python >= 3.11. Every new module starts with `from __future__ import annotations`, matching every existing module in `minigecko/`.
- **Read-only hardware access.** Stage 1 may invoke only `minipro -D` (read chip ID) and `minipro -z` (pin contact check). It must never invoke `-w`, `-E`, `-m`, or any verb that applies programming voltage. There must be no code path from `identify.py` to a write verb.
- **All minipro output arrives on stderr; stdout is empty.** Parse `result.stdout + "\n" + result.stderr`, as `minipro.logic_test` already does at `minigecko/core/minipro.py:349`.
- **`minipro -D` exits 1 on an ID mismatch, and mismatch is the success case.** `_run_subprocess` sets `ok = proc.returncode == 0` (`minigecko/core/minipro.py:112`), so a probe that successfully read the silicon's ID returns `ok=False`. Never gate ID parsing on `result.ok`.
- **Resolve pin count from the package string first, the `pin_count` field second.** The field is scrambled for non-DIP parts (`pin_count == 33` → package `BGA48`; `34` → `BGA63`; `63` → `PLCC32`). It is only trustworthy when the package string is empty.
- Use the `has_chip_id` hardware flag (via `device_db.decode_flags`) as the authority for ID capability, never `chip_id != "0x00000000"`.
- New public names are re-exported from `minigecko/core/__init__.py` and `minigecko/ui/modals/__init__.py`, matching the existing convention ("Import from here, not from submodules").
- Tests go in `tests/test_core.py` and must pass with no programmer attached and no `MINIGECKO_EMULATE` set.
- Run tests with `.venv/bin/python -m pytest`.
- Commit after every task.

---

### Task 1: Package parsing and socket pin resolution

**Files:**
- Create: `minigecko/core/identify.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: `minigecko.core.device_db.get_db`
- Produces:
  - `parse_package(package: str) -> tuple[str | None, int | None]`
  - `package_family(entry: dict) -> str | None`
  - `socket_pins(entry: dict) -> int | None`
  - `DIP_FAMILIES: frozenset[str]`

**Background:** `device_db` entries are dicts with keys including `canonical_names` (list of names), `package` (e.g. `"DIP28"`, `"TSOP32(ADP:Pin9to1)"`, `"BGA100(recommend)"`, or `""`), `pin_count` (int, often `0` or scrambled), `chip_id` (e.g. `"0x01007e22"`), and `type_label`. Get the unique entries with `list({id(v): v for v in get_db().values()}.values())` — `get_db()` maps every name variant to a shared entry dict, so iterating values yields duplicates.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_core.py`:

```python
from minigecko.core.identify import (
    DIP_FAMILIES,
    package_family,
    parse_package,
    socket_pins,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_core.py -k "PackageParsing or SocketPins" -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'minigecko.core.identify'`

- [ ] **Step 3: Write minimal implementation**

Create `minigecko/core/identify.py`:

```python
"""
minigecko.core.identify
~~~~~~~~~~~~~~~~~~~~~~~
Non-destructive identification of ICs whose markings are unreadable.

The engine narrows minipro's device catalogue using what the user can see
(pin count, package presentation, surviving marking characters), then
optionally confirms with a single read-only chip-ID probe.

Hardware access is injected: `identify()` touches the programmer only when a
probe callable is passed in.
"""

from __future__ import annotations

import logging
import re

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
    PLCC32).  ``pin_count`` is only consulted when the package string is
    empty, which is the case for logicic.xml entries where it is reliable.
    """
    _, pins = parse_package(entry.get("package", ""))
    if pins is not None:
        return pins

    raw = entry.get("pin_count") or 0
    if _MIN_PINS <= raw <= _MAX_PINS and raw % 2 == 0:
        return int(raw)
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_core.py -k "PackageParsing or SocketPins" -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add minigecko/core/identify.py tests/test_core.py
git commit -m "feat(identify): add package parsing and socket pin resolution"
```

---

### Task 2: Marking fragment matcher

**Files:**
- Modify: `minigecko/core/identify.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `marking_matches(marking: str, names: list[str]) -> bool`

**Background:** The user may be able to read a few surviving characters. The spec pins the syntax down: shell-glob (`?` = one character, `*` = any run), case-insensitive, matched against every name in `canonical_names`. A fragment containing **no** wildcard is treated as a substring match, because a user typing `74LS` expects it to match `74LS00` — strict glob semantics would match nothing.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_core.py`:

```python
from minigecko.core.identify import marking_matches


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

    def test_matches_any_of_several_names(self):
        assert marking_matches("2764", ["AM2764A", "MBM2764"]) is True

    def test_empty_marking_matches_everything(self):
        assert marking_matches("", ["ANYTHING"]) is True

    def test_whitespace_only_marking_matches_everything(self):
        assert marking_matches("   ", ["ANYTHING"]) is True

    def test_no_names_never_matches(self):
        assert marking_matches("74LS", []) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_core.py -k MarkingMatcher -v`
Expected: FAIL — `ImportError: cannot import name 'marking_matches'`

- [ ] **Step 3: Write minimal implementation**

Add `import fnmatch` to the imports in `minigecko/core/identify.py`, then append:

```python
def marking_matches(marking: str, names: list[str]) -> bool:
    """
    Test a surviving-marking fragment against a device's names.

    Syntax is shell-glob and case-insensitive: ``?`` matches one character,
    ``*`` matches any run.  A fragment with no wildcards is treated as a
    substring match, so "74LS" matches "SN74LS00" the way a user expects.
    An empty or whitespace-only fragment matches everything.
    """
    pattern = (marking or "").strip().upper()
    if not pattern:
        return True

    if "*" not in pattern and "?" not in pattern:
        return any(pattern in (name or "").upper() for name in names)

    return any(fnmatch.fnmatchcase((name or "").upper(), pattern) for name in names)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_core.py -k MarkingMatcher -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add minigecko/core/identify.py tests/test_core.py
git commit -m "feat(identify): add marking fragment glob matcher"
```

---

### Task 3: Chip ID normalisation, reverse index, and probe carriers

**Files:**
- Modify: `minigecko/core/identify.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: `socket_pins`, `package_family`, `DIP_FAMILIES` (Task 1); `device_db.get_db`, `device_db.decode_flags`
- Produces:
  - `normalize_chip_id(raw: str) -> str`
  - `is_id_capable(entry: dict) -> bool`
  - `unique_entries() -> tuple[dict, ...]` (a tuple because it is `lru_cache`d and must be immutable)
  - `chip_id_index() -> dict[str, list[str]]`
  - `probe_carriers(pin_count: int) -> list[str]`

**Background:** IDs are stored 8-hex-wide in `device_db` (`"0x01007e22"`) but minipro reports 4-wide (`"0x0108"`) for some parts, so raw string comparison fails. Normalise by stripping `0x`, upper-casing, and stripping leading zeros — comparing significant digits. IDs are deliberately non-unique: `0x01007e22` is shared by 136 devices, which is why the index maps to a *list*.

`decode_flags(entry)` returns a list of `(key, label, value)` tuples; the ID-capability entry has label `"Chip ID"` and a bool value (see `minigecko/core/device_db.py:89`).

A **probe carrier** is a device used purely as an electrical harness for the ID read. Eligibility requires an exact socket pin-count match, because pin count is the proxy for "VCC and GND land on the same physical socket pins". Carriers must also be ID-capable, be DIP (a carrier defines the socket wiring, so a non-DIP profile is wrong regardless of what the user has on an adapter), and must not be ISP entries (`is_isp` — in-system programming, wired to a target board rather than the socket).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_core.py`:

```python
from minigecko.core.identify import (
    chip_id_index,
    is_id_capable,
    normalize_chip_id,
    probe_carriers,
    unique_entries,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_core.py -k "ChipId or UniqueEntries or ProbeCarriers" -v`
Expected: FAIL — `ImportError: cannot import name 'normalize_chip_id'`

- [ ] **Step 3: Write minimal implementation**

Add `from functools import lru_cache` and `from minigecko.core.device_db import decode_flags, get_db` to the imports in `minigecko/core/identify.py`, then append:

```python
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
def chip_id_index() -> dict[str, list[str]]:
    """
    Reverse index: normalised chip ID -> device names carrying that ID.

    IDs are deliberately non-unique (0x01007e22 is shared by 136 devices), so
    values are lists.  Entries without the has_chip_id flag, and the all-zero
    placeholder ID, are excluded.
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
    return index


def probe_carriers(pin_count: int) -> list[str]:
    """
    Devices usable as an electrical harness for an ID read at *pin_count* pins.

    Eligibility is deliberately strict: an exact pin-count match (the proxy for
    "VCC and GND land on the same socket pins"), a DIP package (a carrier
    defines the socket wiring), chip-ID capability, and not an ISP entry.
    Mismatches are excluded, never merely ranked lower.
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
        names = entry.get("canonical_names") or []
        if names:
            carriers.append(names[0])
    return sorted(carriers)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_core.py -k "ChipId or UniqueEntries or ProbeCarriers" -v`
Expected: PASS (18 tests)

- [ ] **Step 5: Commit**

```bash
git add minigecko/core/identify.py tests/test_core.py
git commit -m "feat(identify): add reverse chip ID index and probe carrier selection"
```

---

### Task 4: Data model and confidence rule

**Files:**
- Modify: `minigecko/core/identify.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `ChipHint(pin_count: int, via_adapter: bool = False, marking: str | None = None)`
  - `Evidence(kind: str, detail: str)`
  - `Candidate(name: str, entry: dict, evidence: list[Evidence])` with `.confidence` property and `.sort_key` property
  - `NextStep(label: str, estimate: str, stage: int, available: bool = False)`
  - `IdentifyReport(candidates: list[Candidate], diagnostics: list[str], suggested_next: list[NextStep], observed_id: str | None = None, carrier: str | None = None)`
  - `EVIDENCE_SILICON_ID`, `EVIDENCE_MARKING`, `EVIDENCE_PACKAGE` string constants
  - `CONFIDENCE_ORDER: dict[str, int]`

**Background:** Evidence is stored as data rather than collapsed into a number so the UI can show *why* a chip was suggested. Confidence is derived from which evidence kinds are present, by a fixed three-way rule with no numeric weights — the spec is explicit that there is no scoring function.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_core.py`:

```python
from minigecko.core.identify import (
    CONFIDENCE_ORDER,
    EVIDENCE_MARKING,
    EVIDENCE_PACKAGE,
    EVIDENCE_SILICON_ID,
    Candidate,
    ChipHint,
    Evidence,
    IdentifyReport,
    NextStep,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_core.py -k "ChipHint or Confidence or ReportModel" -v`
Expected: FAIL — `ImportError: cannot import name 'CONFIDENCE_ORDER'`

- [ ] **Step 3: Write minimal implementation**

Add `from dataclasses import dataclass, field` to the imports in `minigecko/core/identify.py`, then append:

```python
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
    entry: dict
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_core.py -k "ChipHint or Confidence or ReportModel" -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add minigecko/core/identify.py tests/test_core.py
git commit -m "feat(identify): add candidate data model and confidence rule"
```

---

### Task 5: Tier 0 catalogue filter

**Files:**
- Modify: `minigecko/core/identify.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: `socket_pins`, `package_family`, `DIP_FAMILIES`, `marking_matches`, `unique_entries`, `ChipHint`, `Candidate`, `Evidence`, `EVIDENCE_PACKAGE`, `EVIDENCE_MARKING`
- Produces: `tier0_candidates(hint: ChipHint) -> list[Candidate]`

**Background:** Tier 0 touches no hardware at all. It filters to entries whose resolved socket pin count matches exactly, restricted to DIP unless `via_adapter` is set, then applies the marking fragment.

An entry with an **empty** package string has an *unknown* package, not a non-DIP one — and 259 of the 261 logic IC entries are in that group. Excluding them from direct mode would delete every logic IC, so unknown-package entries stay eligible in both modes.

Expect roughly 231 candidates for a bare DIP-28 hint and around 117 for DIP-8; adapter mode widens substantially. Tests assert relative behaviour rather than exact counts, which drift with minipro versions.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_core.py`:

```python
from minigecko.core.identify import tier0_candidates


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_core.py -k Tier0 -v`
Expected: FAIL — `ImportError: cannot import name 'tier0_candidates'`

- [ ] **Step 3: Write minimal implementation**

Append to `minigecko/core/identify.py`:

```python
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

        candidates.append(Candidate(name=names[0], entry=entry, evidence=evidence))

    candidates.sort(key=lambda c: c.sort_key)
    return candidates
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_core.py -k Tier0 -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add minigecko/core/identify.py tests/test_core.py
git commit -m "feat(identify): add tier 0 catalogue filter"
```

---

### Task 6: minipro bridge — chip ID read and pin contact parsing

**Files:**
- Modify: `minigecko/core/minipro.py` (append near `pin_check_device` at line 333)
- Modify: `minigecko/core/emulator.py` (add branch in `emulate`, line ~190)
- Modify: `minigecko/core/__init__.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: `_run`, `MiniproResult` (existing in `minipro.py`)
- Produces:
  - `minipro.read_chip_id(device: str) -> MiniproResult` with `result.data = {"chip_id": str | None, "expected_id": str | None, "matched": bool}`
  - `minipro.parse_bad_pins(text: str) -> list[int]`
  - `minipro.pin_check_device(device)` gains `result.data = {"bad_pins": list[int]}`
  - Both re-exported from `minigecko.core`

**Background — verified against real hardware (minipro 0.7.4, TL866II+ fw 04.2.132, empty socket):**

```
$ minipro -p 'AM2764A@DIP28' -D   # EXIT=1, stdout EMPTY, all output on stderr
Found TL866II+ 04.2.132 (0x284)
Device code: 20763360
Serial code: HXOJSQYX27XG1APKTUKS
USB speed: 12Mbps (USB 1.1)

Chip ID mismatch: expected 0x0108, got 0xFFFF (unknown)
```

```
$ minipro -p 'AM2764A@DIP28' -z   # EXIT=1, stdout EMPTY, all output on stderr
Found TL866II+ 04.2.132 (0x284)
...
Bad contact on pin:1
Bad contact on pin:2
... pins 1-13, 15-25, 27 — 26 lines.  Pins 14 and 26 are absent:
    those are GND and VCC on a DIP-28 profile and are not contact-testable.
```

Three consequences, all load-bearing:

1. Parse `result.stdout + "\n" + result.stderr` — stdout alone is empty.
2. **Never gate on `result.ok`.** Exit 1 on mismatch means a *successful* ID read reports `ok=False`. The parsed `data` is the signal, not `ok`.
3. The "ID actually matches the carrier" wording has **not** been observed (the socket was empty during verification). Treat "no mismatch line present and `returncode == 0`" as the matched case, and set `chip_id=None, matched=True` — the caller already knows the carrier's expected ID from `device_db`, so nothing is lost. Do not invent wording to match against.

Emulator behaviour: emulator mode means "the selected device *is* in the socket", so `-D` returns the matched case.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_core.py`:

```python
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
```

And a test class for the ID parser that drives the real function through a
stubbed transport, so no hardware is needed:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_core.py -k "ParseBadPins or ReadChipId" -v`
Expected: FAIL — `ImportError: cannot import name 'parse_bad_pins'`

- [ ] **Step 3: Write minimal implementation**

In `minigecko/core/minipro.py`, add these two module-level regexes next to `_ANSI_RE` (line 339):

```python
_CHIP_ID_MISMATCH_RE = re.compile(
    r"Chip ID mismatch:\s*expected\s*0x([0-9A-Fa-f]+),\s*got\s*0x([0-9A-Fa-f]+)"
)
_BAD_PIN_RE = re.compile(r"Bad contact on pin:(\d+)")
```

Add `parse_bad_pins` and `read_chip_id`, and extend `pin_check_device`. Replace
the existing `pin_check_device` (line 333) with:

```python
def parse_bad_pins(text: str) -> list[int]:
    """Pin numbers minipro reported as bad contact, sorted and deduplicated."""
    return sorted({int(m.group(1)) for m in _BAD_PIN_RE.finditer(text or "")})


def pin_check_device(device: str) -> MiniproResult:
    """
    Check for bad pin contact on *device*.

    On completion, ``result.data["bad_pins"]`` holds the pin numbers minipro
    flagged.  An empty socket flags every testable pin; supply pins (GND, VCC)
    are never reported because they are not contact-testable.
    """
    result = _run(["-p", device, "-z"])
    result.data = {"bad_pins": parse_bad_pins(result.stdout + "\n" + result.stderr)}
    return result


def read_chip_id(device: str) -> MiniproResult:
    """
    Read the chip ID via ``minipro -p <device> -D`` and nothing else.

    *device* is used purely as an electrical harness: minipro needs a profile
    to know which socket pins carry VCC/GND and which ID protocol to speak.

    On completion, ``result.data`` holds:
      - ``chip_id`` (str | None): the ID the silicon actually reported
      - ``expected_id`` (str | None): the ID *device*'s profile expected
      - ``matched`` (bool): True when the socketed chip IS *device*

    ``result.ok`` is False whenever the ID differs from the carrier's, because
    minipro exits 1 on mismatch — but a mismatch is this function's SUCCESS
    case.  Callers must read ``result.data``, never gate on ``result.ok``.
    """
    result = _run(["-p", device, "-D"])
    text = result.stdout + "\n" + result.stderr

    match = _CHIP_ID_MISMATCH_RE.search(text)
    if match:
        result.data = {
            "expected_id": f"0X{match.group(1).upper()}",
            "chip_id": f"0X{match.group(2).upper()}",
            "matched": False,
        }
    elif result.returncode == 0:
        # No mismatch reported and minipro was happy: the socketed chip is
        # the carrier.  The caller knows the carrier's ID from device_db.
        result.data = {"expected_id": None, "chip_id": None, "matched": True}
    else:
        result.data = {"expected_id": None, "chip_id": None, "matched": False}

    return result
```

In `minigecko/core/emulator.py`, add a `-D` branch inside `emulate`, immediately
before the `if "-z" in args:` branch:

```python
        if "-D" in args:
            return _emu_read_id(device)
```

and add the handler next to `_emu_pin_check`:

```python
def _emu_read_id(device: str) -> MiniproResult:
    """Emulator mode assumes the selected device IS in the socket."""
    return MiniproResult(ok=True, returncode=0, stdout=f"Chip ID OK {device} (emulated)\n")
```

In `minigecko/core/__init__.py`, add `parse_bad_pins` and `read_chip_id` to both
the `from .minipro import (...)` list and `__all__`, keeping alphabetical order.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_core.py -k "ParseBadPins or ReadChipId" -v`
Expected: PASS (9 tests)

Then confirm nothing regressed and the emulator branch works:

Run: `.venv/bin/python -m pytest tests/test_core.py -v`
Expected: PASS (all)

Run: `MINIGECKO_EMULATE=1 .venv/bin/python -c "from minigecko.core import read_chip_id; print(read_chip_id('AM2764A@DIP28').data)"`
Expected: `{'expected_id': None, 'chip_id': None, 'matched': True}`

- [ ] **Step 5: Commit**

```bash
git add minigecko/core/minipro.py minigecko/core/emulator.py minigecko/core/__init__.py tests/test_core.py
git commit -m "feat(minipro): add read_chip_id and bad-pin parsing"
```

---

### Task 7: Socket width from the detected programmer

**Files:**
- Modify: `minigecko/core/identify.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: `minipro.detect_programmer` (returns `ProgrammerInfo(connected, hardware, firmware, raw)`; `hardware` is e.g. `"TL866II+"`)
- Produces:
  - `socket_width(info: ProgrammerInfo | None = None) -> int`
  - `DEFAULT_SOCKET_WIDTH: int`

**Background:** The wizard caps the pin-count input at the socket's physical width so a user cannot ask for a 48-pin identification on a 40-pin socket. TL866II+ and T48 are 40-pin; the T56 is 48-pin. Unknown models fall back to 40, which is the conservative choice — it can only under-offer, never over-offer.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_core.py`:

```python
from minigecko.core.identify import DEFAULT_SOCKET_WIDTH, socket_width
from minigecko.core.minipro import ProgrammerInfo


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_core.py -k SocketWidth -v`
Expected: FAIL — `ImportError: cannot import name 'DEFAULT_SOCKET_WIDTH'`

- [ ] **Step 3: Write minimal implementation**

Add `from minigecko.core.minipro import ProgrammerInfo, detect_programmer` to the
imports in `minigecko/core/identify.py`, then append:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_core.py -k SocketWidth -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add minigecko/core/identify.py tests/test_core.py
git commit -m "feat(identify): derive socket width from detected programmer"
```

---

### Task 8: The identify() orchestrator with Tier 1 probe

**Files:**
- Modify: `minigecko/core/identify.py`
- Modify: `minigecko/core/__init__.py`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: everything from Tasks 1–7
- Produces:
  - `ProbeResult` type alias: `dict` with keys `chip_id`, `expected_id`, `matched`
  - `default_probe(carrier: str) -> dict` — the real hardware path
  - `identify(hint: ChipHint, probe: Callable[[str], dict] | None = None) -> IdentifyReport`
  - `MUTE_IDS: frozenset[str]`
  - `suggested_next_steps(candidates: list[Candidate]) -> list[NextStep]`

**Background and one deliberate deviation from the spec:** the design note says `probe` defaults to the real minipro call. **Change it: `probe=None` means Tier 0 only.** Callers must pass `probe=default_probe` explicitly to energize the socket. This makes "cannot touch hardware by accident" a property of the signature rather than a convention, which is a stronger version of the same safety goal the spec was reaching for. Record this deviation in the commit message.

The probe callable takes only a carrier name and returns only data — there is no payload parameter, so there is no shape of call that could write to a chip.

`0xFFFF` and `0x0000` mean "nothing inserted, or the chip is electrically mute" — verified with an empty socket. They are diagnostics, never matches.

Note that a *matched* probe (`matched=True`) means the socketed chip IS the carrier, so the observed ID is the carrier's own `chip_id` from `device_db`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_core.py`:

```python
from minigecko.core.identify import MUTE_IDS, identify, suggested_next_steps


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
    # that actually intersects a 28-pin hint. Verified against the live DB.
    _SHARED_ID = "0x00000110"

    def test_probe_narrows_to_the_id_group(self):
        probe = lambda carrier: {
            "chip_id": self._SHARED_ID,
            "expected_id": "0x0108",
            "matched": False,
        }
        report = identify(ChipHint(pin_count=28), probe=probe)
        assert report.observed_id == self._SHARED_ID
        assert report.carrier is not None
        assert report.candidates
        assert all(c.confidence == "confirmed" for c in report.candidates)

    def test_probe_result_is_intersected_with_tier0(self):
        probe = lambda carrier: {
            "chip_id": self._SHARED_ID,
            "expected_id": "0x0108",
            "matched": False,
        }
        tier0 = {c.name for c in tier0_candidates(ChipHint(pin_count=28))}
        report = identify(ChipHint(pin_count=28), probe=probe)
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
        assert any("mute" in d.lower() or "inserted" in d.lower() for d in report.diagnostics)
        assert all(c.confidence != "confirmed" for c in report.candidates)

    def test_all_zero_id_is_mute(self):
        assert "0" in MUTE_IDS or normalize_chip_id("0x0000") in MUTE_IDS

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
        # so there is nothing to probe with. Verified against the live DB — do
        # not use 14 here, which has 9 carriers.
        report = identify(ChipHint(pin_count=16), probe=probe)
        assert called == []
        assert report.candidates  # tier 0 still produced a shortlist
        assert any("carrier" in d.lower() for d in report.diagnostics)


class TestSuggestedNextSteps:
    def test_logic_candidates_suggest_the_sweep(self):
        steps = suggested_next_steps(tier0_candidates(ChipHint(pin_count=14)))
        assert any(step.stage == 2 for step in steps)

    def test_steps_carry_estimates(self):
        steps = suggested_next_steps(tier0_candidates(ChipHint(pin_count=14)))
        assert all(step.estimate for step in steps)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_core.py -k "IdentifyTier0Only or IdentifyTier1 or SuggestedNextSteps" -v`
Expected: FAIL — `ImportError: cannot import name 'MUTE_IDS'`

- [ ] **Step 3: Write minimal implementation**

Add `from typing import Callable` to the imports in `minigecko/core/identify.py`
and `from minigecko.core.device_db import get_device` to the existing
`device_db` import line, then append:

```python
# ---------------------------------------------------------------------------
# Tier 1 — silicon ID probe
# ---------------------------------------------------------------------------

# IDs meaning "nothing inserted, or the chip is electrically mute".
# Verified with an empty socket: minipro reports 0xFFFF.
MUTE_IDS = frozenset({normalize_chip_id("0xFFFF"), normalize_chip_id("0x0000")})

ProbeResult = dict


def default_probe(carrier: str) -> ProbeResult:
    """
    The real hardware path: read the chip ID through *carrier*, read-only.

    Takes only a carrier name and returns only data — there is no payload
    parameter, so no call shape can write to the chip.
    """
    from minigecko.core.minipro import read_chip_id

    return read_chip_id(carrier).data or {}


def suggested_next_steps(candidates: list[Candidate]) -> list[NextStep]:
    """
    Deeper passes that could narrow *candidates* further.

    Stage 1 only advertises these; ``available`` stays False until the
    implementing stage lands.
    """
    steps: list[NextStep] = []
    type_labels = {c.entry.get("type_label", "") for c in candidates}

    logic = [c for c in candidates if c.entry.get("type_label") == "Logic IC"]
    if logic:
        steps.append(
            NextStep(
                label=f"Logic vector sweep — {len(logic)} candidates",
                estimate=f"~{max(1, round(len(logic) * 1.5 / 60))} min",
                stage=2,
            )
        )

    if type_labels & {"SRAM", "ROM / EEPROM / Flash"}:
        steps.append(
            NextStep(
                label="Memory capacity profiling",
                estimate="~2 min",
                stage=3,
            )
        )

    return steps


def identify(
    hint: ChipHint,
    probe: Callable[[str], ProbeResult] | None = None,
) -> IdentifyReport:
    """
    Identify the chip described by *hint*, narrowing cheapest-first.

    With *probe* omitted this runs Tier 0 only and touches no hardware — the
    engine cannot energize the socket unless a probe is handed in explicitly.
    Pass ``probe=default_probe`` for the real read-only ID read.

    Failures are reported as diagnostics rather than raised: "couldn't tell"
    is a legitimate outcome.
    """
    diagnostics: list[str] = []
    candidates = tier0_candidates(hint)

    if not candidates:
        diagnostics.append(
            "No candidates matched. Try adapter mode, or relax the marking fragment."
        )

    report = IdentifyReport(
        candidates=candidates,
        diagnostics=diagnostics,
        suggested_next=suggested_next_steps(candidates),
    )

    if probe is None:
        diagnostics.append("Catalogue filter only — no probe supplied, no hardware used.")
        return report

    carriers = probe_carriers(hint.pin_count)
    if not carriers:
        diagnostics.append(
            f"No probe carrier available for {hint.pin_count} pins — "
            "no ID-capable DIP profile of that width exists. Catalogue filter only."
        )
        return report

    carrier = carriers[0]
    report.carrier = carrier

    try:
        probe_data = probe(carrier) or {}
    except Exception as exc:  # hardware and subprocess failures are expected
        diagnostics.append(f"Probe failed via carrier {carrier}: {exc}")
        return report

    if probe_data.get("matched"):
        entry = get_device(carrier)
        observed = (entry or {}).get("chip_id")
        report.observed_id = observed
        diagnostics.append(f"Chip ID matched carrier {carrier} exactly.")
        _confirm(report, [carrier], observed or "carrier match", carrier)
        return report

    raw_id = probe_data.get("chip_id")
    if not raw_id:
        diagnostics.append(
            f"Could not read a chip ID via carrier {carrier}. Catalogue filter only."
        )
        return report

    report.observed_id = raw_id
    key = normalize_chip_id(raw_id)

    if key in MUTE_IDS:
        diagnostics.append(
            f"Read {raw_id} via carrier {carrier} — nothing inserted, or the chip "
            "does not implement an ID command. Catalogue filter only."
        )
        return report

    hits = chip_id_index().get(key)
    if not hits:
        diagnostics.append(
            f"Read chip ID {raw_id} via carrier {carrier}, but no catalogue device "
            "carries it. Search that ID manually. Catalogue filter only."
        )
        return report

    _confirm(report, hits, raw_id, carrier)

    if not any(c.confidence == "confirmed" for c in report.candidates):
        diagnostics.append(
            f"Chip ID {raw_id} matched {len(hits)} catalogue devices, but none of "
            f"them are {hint.pin_count}-pin. The stated pin count may be wrong."
        )

    return report


def _confirm(
    report: IdentifyReport,
    names: list[str],
    observed_id: str,
    carrier: str,
) -> None:
    """
    Attach silicon evidence to candidates whose names appear in *names*, and
    drop the rest.  Intersection is what collapses a shared ID group — some
    IDs are carried by over 100 devices.
    """
    wanted = set(names)
    confirmed = [c for c in report.candidates if c.name in wanted]

    for cand in confirmed:
        cand.evidence.append(
            Evidence(
                kind=EVIDENCE_SILICON_ID,
                detail=f"silicon ID {observed_id} (read via {carrier})",
            )
        )

    if confirmed:
        confirmed.sort(key=lambda c: c.sort_key)
        report.candidates = confirmed
        report.suggested_next = suggested_next_steps(confirmed)
```

In `minigecko/core/__init__.py`, add an identify import block after the
`device_db` block:

```python
from .identify import (
    Candidate,
    ChipHint,
    Evidence,
    IdentifyReport,
    NextStep,
    default_probe,
    identify,
    socket_width,
)
```

and add `"Candidate"`, `"ChipHint"`, `"Evidence"`, `"IdentifyReport"`,
`"NextStep"`, `"default_probe"`, `"identify"`, `"socket_width"` to `__all__` in
alphabetical position.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_core.py -k "IdentifyTier0Only or IdentifyTier1 or SuggestedNextSteps" -v`
Expected: PASS (14 tests)

Run the whole suite and confirm the engine cannot reach a write verb:

Run: `.venv/bin/python -m pytest tests/test_core.py -v`
Expected: PASS (all)

Run: `grep -nE '"-w"|"-E"|"-m"|write_device|erase_device' minigecko/core/identify.py`
Expected: no output — no write verb is reachable from the engine.

- [ ] **Step 5: Commit**

```bash
git add minigecko/core/identify.py minigecko/core/__init__.py tests/test_core.py
git commit -m "feat(identify): add tiered identify() orchestrator with read-only probe

Deviation from the design note: probe=None now means tier 0 only, rather
than defaulting to the real hardware call. Callers must pass
probe=default_probe explicitly, making 'cannot energize by accident' a
property of the signature rather than a convention."
```

---

### Task 9: IdentifyScreen wizard

**Files:**
- Create: `minigecko/ui/modals/identify.py`
- Modify: `minigecko/ui/modals/__init__.py`
- Test: manual (Textual screens are exercised through the app; this repo has no UI test harness)

**Interfaces:**
- Consumes: `ChipHint`, `Candidate`, `IdentifyReport`, `identify`, `default_probe`, `socket_width`, `tier0_candidates`, `probe_carriers` from `minigecko.core.identify`; `pin_check_device` from `minigecko.core`
- Produces: `IdentifyScreen(ModalScreen[str | None])` — dismisses with the chosen device name, or `None` on cancel

**Background:** Follow `minigecko/ui/modals/chip_select.py` for structure: a `ModalScreen` subclass with `DEFAULT_CSS`, `BINDINGS`, `compose()`, and action methods. `ChipSelectScreen` is `ModalScreen[str | None]` and dismisses with the selected device name — match that so the caller's callback shape is identical.

The three steps live in one screen, swapping which container is visible, rather than three pushed screens — that keeps the entered hint alive when the user declines the safety gate and returns to step 1.

Safety sequencing inside `_run_probe`, in this exact order:

1. `pin_check_device(carrier)` — if `result.data["bad_pins"]` is non-empty, abort and show the pin numbers. An empty socket flags every testable pin; a few flagged pins means misalignment. Both are reasons not to energize.
2. Only then call `identify(hint, probe=default_probe)`.

- [ ] **Step 1: Create the screen**

Create `minigecko/ui/modals/identify.py`:

```python
"""Chip identification wizard for ICs with unreadable markings."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DataTable, Footer, Input, Label, Static

from minigecko.core.identify import (
    ChipHint,
    IdentifyReport,
    default_probe,
    identify,
    probe_carriers,
    socket_width,
    tier0_candidates,
)


class IdentifyScreen(ModalScreen[str | None]):
    """
    Three-step wizard: describe the chip, confirm the safety implications,
    review ranked candidates.  Dismisses with the chosen device name.
    """

    DEFAULT_CSS = """
    IdentifyScreen { align: center middle; }
    IdentifyScreen > .id-container {
        width: 80%; height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    IdentifyScreen .id-title { color: $accent; height: 1; margin-bottom: 1; }
    IdentifyScreen .id-hidden { display: none; }
    IdentifyScreen #id-count { color: $text-muted; height: 1; margin-top: 1; }
    IdentifyScreen #id-results { height: 1fr; border: solid $panel; }
    IdentifyScreen #id-diagnostics { color: $warning; height: auto; margin-top: 1; }
    IdentifyScreen #id-next { color: $text-muted; height: auto; margin-top: 1; }
    IdentifyScreen .id-warn { color: $warning; height: auto; }
    IdentifyScreen .id-row { height: 3; margin-top: 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._width = socket_width()
        self._hint: ChipHint | None = None
        self._report: IdentifyReport | None = None

    # -- compose ---------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical(classes="id-container"):
            yield Label("Identify unknown chip", classes="id-title")

            with Vertical(id="id-step-input"):
                yield Label(f"Pin count (8-{self._width}, even):")
                yield Input(placeholder="28", id="id-pins")
                yield Checkbox("Mounted on an adapter (non-DIP part)", id="id-adapter")
                yield Label("Surviving marking characters (optional, ? and * allowed):")
                yield Input(placeholder="74??00", id="id-marking")
                yield Static("", id="id-count")
                with Horizontal(classes="id-row"):
                    yield Button("Probe chip ID", variant="primary", id="id-go")
                    yield Button("Catalogue only", id="id-offline")

            with Vertical(id="id-step-confirm", classes="id-hidden"):
                yield Static("", id="id-confirm-text", classes="id-warn")
                with Horizontal(classes="id-row"):
                    yield Button("Chip is inserted — probe now", variant="warning", id="id-confirm")
                    yield Button("Back", id="id-back")

            with Vertical(id="id-step-results", classes="id-hidden"):
                yield DataTable(id="id-results")
                yield Static("", id="id-diagnostics")
                yield Static("", id="id-next")
                with Horizontal(classes="id-row"):
                    yield Button("Use selected device", variant="primary", id="id-use")
                    yield Button("Start over", id="id-restart")

            yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#id-results", DataTable)
        table.add_columns("Device", "Confidence", "Evidence")
        table.cursor_type = "row"
        self.query_one("#id-pins", Input).focus()

    # -- step switching --------------------------------------------------

    def _show(self, step: str) -> None:
        for name in ("id-step-input", "id-step-confirm", "id-step-results"):
            self.query_one(f"#{name}").set_class(name != step, "id-hidden")

    # -- hint parsing ----------------------------------------------------

    def _read_hint(self) -> ChipHint | None:
        raw = self.query_one("#id-pins", Input).value.strip()
        if not raw.isdigit():
            self.query_one("#id-count", Static).update("Enter a pin count.")
            return None

        pins = int(raw)
        if pins < 8 or pins > self._width or pins % 2:
            self.query_one("#id-count", Static).update(
                f"Pin count must be an even number between 8 and {self._width}."
            )
            return None

        return ChipHint(
            pin_count=pins,
            via_adapter=self.query_one("#id-adapter", Checkbox).value,
            marking=self.query_one("#id-marking", Input).value.strip() or None,
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        hint = self._read_hint()
        if hint is None:
            return
        count = len(tier0_candidates(hint))
        self.query_one("#id-count", Static).update(f"{count} catalogue candidates")

    # -- buttons ---------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id

        if button == "id-offline":
            hint = self._read_hint()
            if hint:
                self._present(identify(hint))

        elif button == "id-go":
            hint = self._read_hint()
            if hint is None:
                return
            from minigecko.core import detect_programmer

            if not detect_programmer().connected:
                report = identify(hint)
                report.diagnostics.insert(
                    0, "No programmer detected — catalogue filter only, nothing probed."
                )
                self._present(report)
                return
            self._hint = hint
            self._prepare_confirm(hint)

        elif button == "id-back":
            self._show("id-step-input")

        elif button == "id-confirm":
            if self._hint:
                self._run_probe(self._hint)

        elif button == "id-restart":
            self._show("id-step-input")

        elif button == "id-use":
            self._use_selection()

    # -- safety gate -----------------------------------------------------

    def _prepare_confirm(self, hint: ChipHint) -> None:
        carriers = probe_carriers(hint.pin_count)
        if not carriers:
            self._present(identify(hint))
            return

        carrier = carriers[0]
        adapter_note = (
            "\n\nAdapter mode: double-check the adapter's own pin-1 orientation too."
            if hint.via_adapter
            else ""
        )
        self.query_one("#id-confirm-text", Static).update(
            f"About to read the chip ID through carrier profile:\n\n"
            f"    {carrier}\n\n"
            f"This applies supply voltage to the {hint.pin_count}-pin DIP power pins "
            f"and reads the ID only — nothing is written or erased.\n\n"
            f"Align pin 1 towards the socket lever. If the chip is a different pin "
            f"count than {hint.pin_count}, power could land on a signal pin.\n\n"
            f"Pin contact is checked first and the probe aborts if any pin is bad."
            f"{adapter_note}"
        )
        self._show("id-step-confirm")

    def _run_probe(self, hint: ChipHint) -> None:
        from minigecko.core import pin_check_device

        carriers = probe_carriers(hint.pin_count)
        carrier = carriers[0]

        contact = pin_check_device(carrier)
        bad = (contact.data or {}).get("bad_pins") or []
        if bad:
            report = identify(hint)
            if len(bad) > hint.pin_count - 4:
                report.diagnostics.insert(
                    0, "Every testable pin reports bad contact — no chip inserted."
                )
            else:
                pins = ", ".join(str(p) for p in bad)
                report.diagnostics.insert(
                    0,
                    f"Bad contact on pin(s) {pins} — reseat the chip. Probe aborted.",
                )
            self._present(report)
            return

        self._present(identify(hint, probe=default_probe))

    # -- results ---------------------------------------------------------

    def _present(self, report: IdentifyReport) -> None:
        self._report = report

        table = self.query_one("#id-results", DataTable)
        table.clear()
        for cand in report.candidates[:200]:
            table.add_row(cand.name, cand.confidence, cand.evidence_summary)

        self.query_one("#id-diagnostics", Static).update("\n".join(report.diagnostics))

        if report.suggested_next:
            lines = [
                f"  · {step.label} ({step.estimate}) — coming in a later release"
                for step in report.suggested_next
            ]
            self.query_one("#id-next", Static).update(
                "Deeper passes available for this chip:\n" + "\n".join(lines)
            )
        else:
            self.query_one("#id-next", Static).update("")

        self._show("id-step-results")
        table.focus()

    def _use_selection(self) -> None:
        table = self.query_one("#id-results", DataTable)
        if self._report is None or not self._report.candidates:
            return
        row = table.cursor_row
        if row is None or row >= len(self._report.candidates):
            return
        self.dismiss(self._report.candidates[row].name)

    def action_cancel(self) -> None:
        self.dismiss(None)
```

- [ ] **Step 2: Verify it imports and constructs**

Run: `.venv/bin/python -c "from minigecko.ui.modals.identify import IdentifyScreen; IdentifyScreen(); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Export it**

In `minigecko/ui/modals/__init__.py`, add the import and `__all__` entry in
alphabetical position:

```python
from minigecko.ui.modals.identify import IdentifyScreen
```

- [ ] **Step 4: Verify the export**

Run: `.venv/bin/python -c "from minigecko.ui.modals import IdentifyScreen; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add minigecko/ui/modals/identify.py minigecko/ui/modals/__init__.py
git commit -m "feat(ui): add IdentifyScreen chip identification wizard"
```

---

### Task 10: Wire the wizard into the app

**Files:**
- Modify: `minigecko/ui/app_shell.py` (BINDINGS at line 36-44; add an action method near `action_select_ic` around line 211)
- Test: manual, via the emulator

**Interfaces:**
- Consumes: `IdentifyScreen` from `minigecko.ui.modals`
- Produces: `MiniGeckoApp.action_identify_ic()` and an `i` keybinding

**Background:** `_open_chip_select` at `minigecko/ui/app_shell.py:200` pushes `ChipSelectScreen()` with an `_on_selected` callback. `IdentifyScreen` dismisses with the same `str | None` shape, so the callback body is identical — an identified chip must behave exactly like a manually selected one (toolbar label updated, IC Ops button enabled, info panel shown, action logged). Existing single-letter bindings are `f`, `s`, `d`, `v`, `h`; `i` is free.

**Deviation from the spec, deliberate:** the design note says selection "sets the active device in `ui/state.py` and hands off to `ICOpsScreen`". Both details were wrong about this codebase. `ui/state.py` only persists panel geometry and the minipro path — the active device lives in `MiniGeckoApp._selected_ic`. And auto-pushing `ICOpsScreen` would make identification behave differently from manual selection; `action_ic_ops` is already reachable with `d` once a device is selected, and `check_action` enables it automatically. So: mirror `_open_chip_select` exactly and do not push `ICOpsScreen`.

- [ ] **Step 1: Confirm the callback body still matches**

Run: `sed -n 200,213p minigecko/ui/app_shell.py`

Expected: the `_on_selected` closure shown in Step 3 below. If it has drifted,
use what is actually there — the requirement is that identify and manual
selection produce identical app state.

- [ ] **Step 2: Add the binding**

In the `BINDINGS` list at `minigecko/ui/app_shell.py:36`, add after the
`Binding("s", "select_ic", "Select IC")` line:

```python
        Binding("i", "identify_ic", "Identify"),
```

- [ ] **Step 3: Add the action method**

Add immediately after `action_select_ic` (which sits at line 213, right after
`_open_chip_select`):

```python
    def action_identify_ic(self) -> None:
        """Identify a chip whose markings are unreadable, then select it."""
        from minigecko.ui.modals import IdentifyScreen

        def _on_identified(chip: str | None) -> None:
            if chip:
                self._selected_ic = chip
                self.query_one("#btn-select-ic", Static).update(f"Selected IC: {chip}")
                btn = self.query_one("#btn-ic-ops", Static)
                btn.remove_class("tb-btn-disabled")
                btn.add_class("tb-btn")
                self.query_one(ICInfoPanel).show(chip)
                self.log_action(f"[green]IC  identified[/]  {chip}")

        self.push_screen(IdentifyScreen(), _on_identified)
```

`Static` and `ICInfoPanel` are already imported at the top of `app_shell.py` —
no new imports are needed beyond the local `IdentifyScreen` one.

- [ ] **Step 4: Verify in the emulator**

Run: `MINIGECKO_EMULATE=1 timeout 10 .venv/bin/python -m minigecko 2>&1 | head -5`
Expected: the app starts without a traceback.

Then confirm the whole suite still passes:

Run: `.venv/bin/python -m pytest tests/test_core.py -v`
Expected: PASS (all)

Run: `.venv/bin/python -c "
from minigecko.core import identify, ChipHint
r = identify(ChipHint(pin_count=28, marking='2764'))
print(len(r.candidates), 'candidates')
print(r.candidates[0].name, r.candidates[0].confidence, r.candidates[0].evidence_summary)
"`
Expected: a non-zero candidate count and a `probable` top candidate with marking evidence.

- [ ] **Step 5: Commit**

```bash
git add minigecko/ui/app_shell.py
git commit -m "feat(ui): wire identify wizard to the 'i' keybinding"
```

---

## Hardware verification (after Task 10, requires a chip in the socket)

The design's one unobserved behaviour is what minipro prints when the chip ID
**matches** the carrier — verification was done on an empty socket. Confirm it
with a known chip:

- [ ] Insert a chip whose identity you know into the ZIF socket, pin 1 to the lever.
- [ ] Run: `minipro -p '<that device>' -D; echo "EXIT=$?"` and record stdout, stderr, and the exit code.
- [ ] If a mismatch line is absent and the exit code is 0, Task 6's matched-case
      branch is already correct — no change needed.
- [ ] If minipro prints something else (a distinct "Chip ID OK" line, or a
      non-zero exit on success), update `read_chip_id`'s matched-case detection
      and add a regression test with the real text, then update the MEMEX note
      `chip-identifier-hardware-verified-minipro-behaviour.md`.
- [ ] Run the wizard end-to-end on that chip: `.venv/bin/python -m minigecko`,
      press `i`, enter its pin count, probe, and confirm it appears as
      `confirmed`.
- [ ] Run the wizard on a genuinely faint-marked chip and record whether the
      shortlist is usable. Note the result on MINIGECKO-005.
