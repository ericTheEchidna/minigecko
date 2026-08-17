"""Chip identification wizard for ICs with unreadable markings."""

from __future__ import annotations

from textual import work
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
    IdentifyScreen #id-total { color: $text-muted; height: 1; margin-top: 1; }
    IdentifyScreen #id-diagnostics { color: $warning; height: auto; margin-top: 1; }
    IdentifyScreen #id-next { color: $text-muted; height: auto; margin-top: 1; }
    IdentifyScreen .id-warn { color: $warning; height: auto; }
    IdentifyScreen .id-row { height: 3; margin-top: 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    _MAX_ROWS = 200

    def __init__(self) -> None:
        super().__init__()
        self._width = socket_width()
        self._hint: ChipHint | None = None
        self._carrier: str | None = None
        self._probing = False
        self._report: IdentifyReport | None = None

    # -- compose ---------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical(classes="id-container"):
            yield Label("Identify unknown chip", classes="id-title")

            with Vertical(id="id-step-input"):
                yield Label(f"Pin count (8-{self._width}, even):")
                yield Input(placeholder="28", type="integer", id="id-pins")
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
                    yield Button(
                        "Chip is inserted — probe now", variant="warning", id="id-confirm"
                    )
                    yield Button("Back", id="id-back")

            with Vertical(id="id-step-results", classes="id-hidden"):
                yield DataTable(id="id-results")
                yield Static("", id="id-total")
                yield Static("", id="id-diagnostics")
                yield Static("", id="id-next")
                with Horizontal(classes="id-row"):
                    yield Button("Use selected device", variant="primary", id="id-use")
                    yield Button("Start over", id="id-restart")

            yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#id-results", DataTable)
        table.add_columns("Device", "Package", "Confidence", "Evidence")
        table.cursor_type = "row"
        self.query_one("#id-pins", Input).focus()

    # -- step switching --------------------------------------------------

    def _show(self, step: str) -> None:
        for name in ("id-step-input", "id-step-confirm", "id-step-results"):
            self.query_one(f"#{name}").set_class(name != step, "id-hidden")

    # -- hint parsing ----------------------------------------------------

    def _read_hint(self) -> ChipHint | None:
        raw = self.query_one("#id-pins", Input).value.strip()
        # isascii() first: "²".isdigit() is True but int("²") raises, and "٣"
        # would silently mean 3.
        if not (raw.isascii() and raw.isdigit()):
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

    def _refresh_count(self) -> None:
        hint = self._read_hint()
        if hint is not None:
            self._count_candidates(hint)

    @work(thread=True, exclusive=True)
    def _count_candidates(self, hint: ChipHint) -> None:
        # Tier 0 only: no probe argument, so this live count never energizes the
        # socket.  Threaded and exclusive because adapter mode costs ~0.27 s per
        # keystroke, which queues up as visible lag on the main thread.
        count = len(tier0_candidates(hint))
        self.app.call_from_thread(
            self.query_one("#id-count", Static).update, f"{count} catalogue candidates"
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        self._refresh_count()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self._refresh_count()

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
            self._prepare_confirm(hint)

        elif button == "id-back":
            self._back_to_input()

        elif button == "id-confirm":
            # One press, one energization.  Two clicks land as two queued
            # messages before either is handled, so disabling the button is not
            # enough on its own — the flag is what the second message sees.
            if self._probing:
                return
            self._probing = True
            event.button.disabled = True
            if self._hint and self._carrier:
                self._run_probe(self._hint, self._carrier)

        elif button == "id-restart":
            self._back_to_input()

        elif button == "id-use":
            self._use_selection()

    # -- safety gate -----------------------------------------------------

    def _back_to_input(self) -> None:
        """Return to step 1, discarding any consent already given."""
        self._hint = None
        self._carrier = None
        self._probing = False
        self.query_one("#id-confirm", Button).disabled = False
        self._show("id-step-input")

    def _prepare_confirm(self, hint: ChipHint) -> None:
        carriers = probe_carriers(hint.pin_count)
        if not carriers:
            # 10, 12, 16, 22, 24, 26, 30, 34, 36 and 38 pins have no carrier, and
            # the user did ask for a probe, so say why there wasn't one.
            report = identify(hint)
            report.diagnostics.insert(
                0,
                f"No probe carrier available for {hint.pin_count} pins — no "
                "ID-capable DIP profile of that width exists. Nothing was "
                "energized.",
            )
            self._present(report)
            return

        carrier = carriers[0]
        # Set only on the branch that reaches the confirm step, so _run_probe can
        # never see a hint the user was not shown a gate for.
        self._hint = hint
        self._carrier = carrier
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
            f"Pin contact is checked first and the probe only runs if that check "
            f"confirms good contact."
            f"{adapter_note}"
        )
        self._show("id-step-confirm")

    @work(thread=True)
    def _run_probe(self, hint: ChipHint, carrier: str) -> None:
        from minigecko.core import pin_check_device

        # Threaded: each minipro call can block for the full 120 s subprocess
        # timeout, and the main thread must stay free to repaint and to service
        # the escape binding while a chip is energized.  Every widget mutation
        # goes back through call_from_thread.

        # Contact first, probe second — never the other way round.  The gate is
        # positive and needs both signals: ok is only returncode == 0, while
        # bad_pins comes from parsed output, so neither alone is sufficient.
        try:
            contact = pin_check_device(carrier)
        except Exception as exc:  # hardware and subprocess failures are expected
            report = identify(hint)
            report.diagnostics.insert(
                0, f"Pin contact check failed, so nothing was energized: {exc}"
            )
            self.app.call_from_thread(self._present, report)
            return

        bad = (contact.data or {}).get("bad_pins") or []
        if contact.ok and not bad:
            self.app.call_from_thread(self._present, identify(hint, probe=default_probe))
            return

        report = identify(hint)
        if not bad:
            # -z is unavailable or errored, so the contact state is unknown.  For
            # some device classes this is simply how minipro behaves.
            report.diagnostics.insert(
                0,
                "Pin contact could not be verified, so nothing was energized: "
                f"{contact.output}",
            )
        elif len(bad) > hint.pin_count - 4:
            # The supply pins are not contact-testable, so an empty socket flags
            # every pin except those.
            report.diagnostics.insert(
                0, "Every testable pin reports bad contact — no chip inserted."
            )
        else:
            pins = ", ".join(str(p) for p in bad)
            report.diagnostics.insert(
                0,
                f"Bad contact on pin(s) {pins} — reseat the chip. Probe aborted.",
            )
        self.app.call_from_thread(self._present, report)

    # -- results ---------------------------------------------------------

    def _present(self, report: IdentifyReport) -> None:
        self._report = report

        table = self.query_one("#id-results", DataTable)
        table.clear()
        for cand in report.candidates[:self._MAX_ROWS]:
            # Package comes from the ENTRY, never parsed out of cand.name: the
            # name is picked for addressability and its suffix can disagree with
            # the entry's real package.
            table.add_row(
                cand.name,
                cand.entry.get("package") or "unknown",
                cand.confidence,
                cand.evidence_summary,
            )

        # The table is capped, so the count states the real total: a truncated
        # table must never read as the whole answer.
        total = len(report.candidates)
        shown = min(total, self._MAX_ROWS)
        suffix = f" — showing the first {shown}" if total > shown else ""
        self.query_one("#id-total", Static).update(
            f"{total:,} candidate{'s' if total != 1 else ''}{suffix}"
        )

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
