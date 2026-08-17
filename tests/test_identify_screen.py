"""
Consent-flow tests for IdentifyScreen, driven through a Textual Pilot.

This screen is the only place in the project that energizes a socket from a UI
consent, so the assertions here are mostly about what does *not* happen: which
contact states reach a probe, and how many probes one consent can start.

The minipro boundary is stubbed at ``minigecko.core.pin_check_device`` and
``minigecko.ui.modals.identify.default_probe``, which are the only two paths the
screen uses to touch hardware, so no test here can reach a real programmer.
"""

from __future__ import annotations

import time

import pytest
from textual.app import App
from textual.widgets import Button, Checkbox, DataTable, Input, Static

import minigecko.core as core
from minigecko.core.minipro import MiniproResult, ProgrammerInfo
from minigecko.ui.modals import identify as identify_mod
from minigecko.ui.modals.identify import IdentifyScreen

# A DIP-28 carrier exists, so 28 pins reaches the confirm step.
PINS = "28"
# No ID-capable DIP profile is 24 pins wide.
PINS_WITHOUT_CARRIER = "24"

GOOD_CONTACT = MiniproResult(ok=True, returncode=0, data={"bad_pins": []})

# An ID carried by several DIP-28 catalogue devices, so a good read confirms.
CONFIRMING_ID = "0x00000110"

# What an empty 28-pin socket really reports: every pin except the two that are
# not contact-testable.
ALL_TESTABLE_PINS_BAD = [pin for pin in range(1, 29) if pin not in (14, 28)]

_UNSET = object()


class _Hardware:
    """Stand-in for the two minipro calls the screen can make."""

    def __init__(self) -> None:
        self.pin_checks: list[str] = []
        self.probes: list[str] = []
        self.contact = GOOD_CONTACT
        self.pin_check_delay = 0.0

    def pin_check_device(self, name: str) -> MiniproResult:
        self.pin_checks.append(name)
        if self.pin_check_delay:
            time.sleep(self.pin_check_delay)
        return self.contact

    def probe(self, carrier: str) -> dict:
        self.probes.append(carrier)
        return {"chip_id": CONFIRMING_ID}


class _Harness(App):
    """Minimal host for the modal, recording what it dismisses with."""

    def __init__(self) -> None:
        super().__init__()
        self.dismissed: object = _UNSET

    def on_mount(self) -> None:
        self.push_screen(IdentifyScreen(), callback=self._record)

    def _record(self, value: str | None) -> None:
        self.dismissed = value


@pytest.fixture
def hardware(monkeypatch: pytest.MonkeyPatch) -> _Hardware:
    hw = _Hardware()
    monkeypatch.setattr(core, "pin_check_device", hw.pin_check_device)
    monkeypatch.setattr(identify_mod, "default_probe", hw.probe)

    # Both the "is anything attached" check and socket_width() shell out to
    # minipro otherwise.
    attached = ProgrammerInfo(connected=True, firmware="04.2.132", hardware="TL866II+")
    monkeypatch.setattr(core, "detect_programmer", lambda: attached)
    monkeypatch.setattr(identify_mod, "socket_width", lambda: 40)
    return hw


def diagnostics(screen: IdentifyScreen) -> str:
    return screen.query_one("#id-diagnostics", Static).visual.plain


async def enter_pins(pilot, value: str) -> IdentifyScreen:
    screen = pilot.app.screen
    screen.query_one("#id-pins", Input).value = value
    await pilot.pause()
    return screen


async def settle(pilot, screen: IdentifyScreen, timeout: float = 10.0) -> None:
    """Wait until no probe is in flight."""
    deadline = time.monotonic() + timeout
    while screen._probing and time.monotonic() < deadline:
        await pilot.pause(0.02)
    assert not screen._probing, "probe worker did not finish"
    await pilot.pause()


async def consent_and_probe(pilot, screen: IdentifyScreen) -> None:
    screen.query_one("#id-go", Button).press()
    await pilot.pause()
    screen.query_one("#id-confirm", Button).press()
    await settle(pilot, screen)


# -- the contact gate ----------------------------------------------------

@pytest.mark.parametrize(
    "contact,expected_probes",
    [
        pytest.param(GOOD_CONTACT, 1, id="ok-and-no-bad-pins"),
        pytest.param(
            MiniproResult(ok=True, returncode=0, data={"bad_pins": [3, 7]}),
            0,
            id="ok-but-bad-pins-reported",
        ),
        pytest.param(
            MiniproResult(ok=False, returncode=1, data={"bad_pins": [3, 7]}),
            0,
            id="failed-with-bad-pins",
        ),
        pytest.param(
            MiniproResult(ok=False, returncode=1, data={"bad_pins": ALL_TESTABLE_PINS_BAD}),
            0,
            id="failed-every-testable-pin",
        ),
        pytest.param(
            MiniproResult(
                ok=False,
                returncode=1,
                stdout="Pin test is not available for this chip.",
                data={"bad_pins": []},
            ),
            0,
            id="failed-without-bad-pins",
        ),
    ],
)
async def test_only_verified_contact_reaches_the_probe(
    hardware: _Hardware, contact: MiniproResult, expected_probes: int
) -> None:
    hardware.contact = contact
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, PINS)
        await consent_and_probe(pilot, screen)

        assert len(hardware.pin_checks) == 1
        assert len(hardware.probes) == expected_probes


@pytest.mark.parametrize(
    "contact,expected",
    [
        pytest.param(
            MiniproResult(ok=True, returncode=0, data={"bad_pins": [3, 7]}),
            "Bad contact on pin(s) 3, 7",
            id="ok-but-bad-pins-reported",
        ),
        pytest.param(
            MiniproResult(ok=False, returncode=1, data={"bad_pins": [3, 7]}),
            "Bad contact on pin(s) 3, 7",
            id="failed-with-bad-pins",
        ),
        pytest.param(
            MiniproResult(ok=False, returncode=1, data={"bad_pins": ALL_TESTABLE_PINS_BAD}),
            "no chip inserted",
            id="failed-every-testable-pin",
        ),
        pytest.param(
            MiniproResult(
                ok=False,
                returncode=1,
                stdout="Pin test is not available for this chip.",
                data={"bad_pins": []},
            ),
            "Pin contact could not be verified",
            id="failed-without-bad-pins",
        ),
    ],
)
async def test_aborted_probe_explains_itself(
    hardware: _Hardware, contact: MiniproResult, expected: str
) -> None:
    hardware.contact = contact
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, PINS)
        await consent_and_probe(pilot, screen)

        assert expected in diagnostics(screen)


async def test_a_raising_pin_check_aborts_instead_of_probing(
    hardware: _Hardware, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(name: str) -> MiniproResult:
        raise OSError("usb went away")

    monkeypatch.setattr(core, "pin_check_device", _boom)
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, PINS)
        await consent_and_probe(pilot, screen)

        assert hardware.probes == []
        assert "nothing was energized" in diagnostics(screen)


async def test_verified_contact_confirms_candidates(hardware: _Hardware) -> None:
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, PINS)
        await consent_and_probe(pilot, screen)

        assert any(c.confidence == "confirmed" for c in screen._report.candidates)


# -- one consent, one energization ---------------------------------------

async def test_double_press_runs_one_probe(hardware: _Hardware) -> None:
    """Both presses queue before either is handled, so the flag is the guard."""
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, PINS)
        screen.query_one("#id-go", Button).press()
        await pilot.pause()

        confirm = screen.query_one("#id-confirm", Button)
        confirm.press()
        confirm.press()
        await settle(pilot, screen)

        assert len(hardware.pin_checks) == 1
        assert len(hardware.probes) == 1


async def test_second_consent_cannot_overlap_an_in_flight_probe(
    hardware: _Hardware,
) -> None:
    """
    Going back mid-probe must not re-arm the gate: the worker still holds the
    socket, and two minipro processes must never race one programmer.
    """
    hardware.pin_check_delay = 0.3
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, PINS)
        screen.query_one("#id-go", Button).press()
        await pilot.pause()
        screen.query_one("#id-confirm", Button).press()
        await pilot.pause()
        assert screen._probing

        # Back to step 1 and consent a second time while probe one is running.
        screen.query_one("#id-back", Button).press()
        await pilot.pause()
        screen.query_one("#id-go", Button).press()
        await pilot.pause()
        screen.query_one("#id-confirm", Button).press()
        await pilot.pause()

        await settle(pilot, screen)

        assert len(hardware.pin_checks) == 1
        assert len(hardware.probes) == 1


async def test_a_retired_probe_does_not_hijack_the_screen(hardware: _Hardware) -> None:
    """A report from a probe the user walked away from must not be presented."""
    hardware.pin_check_delay = 0.3
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, PINS)
        screen.query_one("#id-go", Button).press()
        await pilot.pause()
        screen.query_one("#id-confirm", Button).press()
        await pilot.pause()

        screen.query_one("#id-back", Button).press()
        await pilot.pause()
        await settle(pilot, screen)

        assert screen._report is None
        assert screen.query_one("#id-step-results").has_class("id-hidden")
        assert not screen.query_one("#id-step-input").has_class("id-hidden")
        # The socket is free again, so the gate is re-armed.
        assert not screen.query_one("#id-confirm", Button).disabled


async def test_cancel_is_held_while_a_probe_is_running(hardware: _Hardware) -> None:
    hardware.pin_check_delay = 0.3
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, PINS)
        screen.query_one("#id-go", Button).press()
        await pilot.pause()
        screen.query_one("#id-confirm", Button).press()
        await pilot.pause()

        screen.action_cancel()
        await pilot.pause()
        assert pilot.app.dismissed is _UNSET
        assert screen.is_mounted

        await settle(pilot, screen)
        screen.action_cancel()
        await pilot.pause()
        assert pilot.app.dismissed is None


# -- step 1 ---------------------------------------------------------------

async def test_width_without_a_carrier_says_why(hardware: _Hardware) -> None:
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, PINS_WITHOUT_CARRIER)
        screen.query_one("#id-go", Button).press()
        await pilot.pause()

        assert "No probe carrier available for 24 pins" in diagnostics(screen)
        assert hardware.pin_checks == []
        assert hardware.probes == []
        # No consent was taken, so none is left recorded.
        assert screen._hint is None
        assert screen._carrier is None


async def test_non_ascii_digits_are_rejected(hardware: _Hardware) -> None:
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, "²")
        assert screen._read_hint() is None
        assert "Enter a pin count." in screen.query_one("#id-count", Static).visual.plain


async def test_adapter_checkbox_refreshes_the_candidate_count(
    hardware: _Hardware,
) -> None:
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, "8")
        direct = await _await_count(pilot, screen)

        screen.query_one("#id-adapter", Checkbox).value = True
        adapter = await _await_count(pilot, screen, differs_from=direct)

        # Adapter mode admits non-DIP packages, so it can only widen the field.
        assert adapter > direct


async def _await_count(
    pilot, screen: IdentifyScreen, differs_from: int | None = None
) -> int:
    """Wait for the threaded live count to land, and return it."""
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        await pilot.pause(0.02)
        text = screen.query_one("#id-count", Static).visual.plain
        if "catalogue candidates" in text:
            value = int(text.split()[0])
            if differs_from is None or value != differs_from:
                return value
    raise AssertionError(f"live count never settled (last: {text!r})")


# -- results --------------------------------------------------------------

async def test_package_column_comes_from_the_entry(hardware: _Hardware) -> None:
    """
    A candidate's name is chosen for addressability, so its "@PACKAGE" suffix can
    disagree with the entry's real package.  The table must show the entry's.

    Adapter DIP-8 is the hint that puts real disagreements (24C08@TSSOP8 on a
    SOIC8 entry) inside the displayed rows; on most widths the two agree
    everywhere, which would make this test vacuous.
    """
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, "8")
        screen.query_one("#id-adapter", Checkbox).value = True
        await pilot.pause()
        screen.query_one("#id-offline", Button).press()
        await pilot.pause()

        table = screen.query_one("#id-results", DataTable)
        rows = range(table.row_count)
        shown = [table.get_row_at(row)[1] for row in rows]
        candidates = screen._report.candidates[: table.row_count]
        assert shown == [cand.entry.get("package") or "unknown" for cand in candidates]

        # Guard against the assertion above passing only because nothing differs.
        disagreeing = [
            cand.name
            for cand in candidates
            if cand.name.partition("@")[2] != (cand.entry.get("package") or "")
        ]
        assert disagreeing, "no name/entry package disagreement in view — test is vacuous"


async def test_truncated_table_still_reports_the_true_total(
    hardware: _Hardware,
) -> None:
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, PINS)
        screen.query_one("#id-offline", Button).press()
        await pilot.pause()

        total = len(screen._report.candidates)
        table = screen.query_one("#id-results", DataTable)
        assert table.row_count == min(total, IdentifyScreen._MAX_ROWS)
        assert f"{total:,} candidates" in screen.query_one("#id-total", Static).visual.plain


async def test_use_selected_dismisses_with_the_cursor_row_device(
    hardware: _Hardware,
) -> None:
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, PINS)
        screen.query_one("#id-offline", Button).press()
        await pilot.pause()

        table = screen.query_one("#id-results", DataTable)
        table.move_cursor(row=3)
        await pilot.pause()
        expected = screen._report.candidates[3].name

        screen.query_one("#id-use", Button).press()
        await pilot.pause()
        assert pilot.app.dismissed == expected


async def test_catalogue_only_never_touches_hardware(hardware: _Hardware) -> None:
    async with _Harness().run_test() as pilot:
        screen = await enter_pins(pilot, PINS)
        screen.query_one("#id-offline", Button).press()
        await pilot.pause()

        assert hardware.pin_checks == []
        assert hardware.probes == []
