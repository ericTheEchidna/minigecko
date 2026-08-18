# TASKS.md — minigecko

Generated from MEMEX task database. **Do not hand-edit** — changes will be overwritten.
Update tasks via API: `http://miso:8002/tasks/{task_code}`

---

## How to work tasks

1. **Pick a task** — only work the task(s) explicitly stated at session start.
2. **Mark it active** — `PATCH http://miso:8002/tasks/{code}` with `{"status": "in_progress"}`.
3. **Implement it** — stay focused on the task scope. Do not go on extended research tangents,
   refactor unrelated code, or explore topics beyond what's needed to complete the task.
   If something is unclear or under-specified, **ask for clarification** rather than guessing.
4. **Mark it done** — `PATCH` with `{"status": "done"}` when all done-when criteria are met.
5. **New work discovered?** — Create a new task via `POST http://miso:8002/tasks`.
   Do not expand the current task's scope.

**Key rules:**
- The `body` field contains the full scope, subtasks, and done-when criteria. Read it carefully.
- Do not do extensive research or go far afield from the implementation unless the task explicitly asks for it.
- If the task description is ambiguous or missing context, stop and ask — do not assume.
- One task at a time. Finish or pause before starting another.

---

## Open

### MINIGECKO-00B — Probe carrier selection is alphabetical and voltage-blind

**Priority:** high

Raised by the final whole-branch review of MINIGECKO-005 (chip identifier Stage 1). Depends on
having hardware to hand.

## The gap

`identify.probe_carriers` filters correctly and strictly on the axis it knows about — exact pin
count, DIP family, ID-capable, non-ISP — and pin count is the accepted proxy for "VCC and GND land
on the same physical socket pins". The caller then takes `probe_carriers(pin_count)[0]`, which is
**alphabetically first**, with no consideration of what the chosen profile's ID protocol actually
drives on which pin.

For the two commonest widths that lands on:

- 28 pins → `27128@DIP28`
- 40 pins → `27C210@DIP40`

Both are 27-series EPROMs, and a 27-series **electronic signature** read conventionally requires an
elevated voltage (historically ~12 V) on an address pin — A9 on many parts — rather than VCC alone.
Nobody has verified what `minipro -D` actually drives for those profiles.

If it does raise a programming-adjacent voltage on a signal pin, the practical risk is damage to
the unknown chip the user is trying to rescue. Read-only with respect to chip *contents* is not the
same as electrically gentle.

The `voltages` field is present on every `device_db` entry and is currently unused by carrier
selection.

## Already done (not this task)

The consent text was corrected to stop claiming that only the power pins are energized — it now
states which carrier profile governs the socket and that MiniGecko issues only minipro's read-ID
command. That is honest, but it is a disclosure, not a mitigation.

## What to do

1. **Observe, first.** With an ID-capable DIP part seated, capture `minipro -p '<27-series
   carrier>' -D` and, if the programmer or minipro exposes it, whatever voltage/pin telemetry is
   available. Compare against a carrier whose ID read is logic-level (a 24C-series EEPROM, a
   29F/39SF flash, an ATmega or PIC). The question to answer: does `-D` on a 27-series profile
   raise any pin above Vcc?
2. **If it does**, add a preferred-carrier ordering to `probe_carriers` — rank families whose ID
   read is logic-level ahead of 27-series parts, keeping the current strict eligibility filter
   unchanged and falling back to the existing alphabetical order when no preferred family exists at
   that width. Do not weaken the pin-count/DIP/ID-capable/non-ISP exclusions; this is a preference
   layer on top.
3. **If it does not**, record that finding in the hardware-verified MEMEX note and tighten the
   consent text to say so positively — the current wording is deliberately vague because we do not
   know, and that vagueness is itself a small cost.
4. Either way, consider surfacing the carrier's `voltages` field in the consent step, so the user
   can see what the profile declares.

## Done when

- The hardware-verified note records what `-D` drives on a 27-series profile.
- `probe_carriers`' ordering is either justified in a comment as safe, or changed to prefer
  logic-level ID families with a test pinning the preference at 28 and 40 pins.
- The consent text says what is then actually known.


### MINIGECKO-00A — No app-wide serialization of minipro access

**Priority:** high

Found during the Task 9 review of MINIGECKO-005 (chip identifier Stage 1).

## The defect

`minigecko/core/minipro.py` has no locking of any kind — no `threading.Lock`, no file lock, no
queue. Every long operation in the app runs in a `@work(thread=True)` Textual worker
(`app_shell.py` reads, writes, erases, logic tests, the programmer poll; and now the identify
screen's probe), and nothing prevents two of those workers from having a `minipro` subprocess in
flight at the same time against **one USB programmer with a chip in the socket**.

The identify screen's own instance of this was fixed in-screen (a `_probing` flag cleared on
worker completion), but that guard is local. A probe worker that outlives its screen — the user
presses `escape` mid-probe, the screen is dismissed, the subprocess keeps running — can still
overlap an `app_shell.py` read or erase worker started immediately afterwards.

## Why it matters

Two concurrent `minipro` invocations mean two processes claiming the same USB device and, worse,
two independent decisions about what voltage to apply to which socket pin. The failure modes
range from a confusing USB error to genuinely applying conflicting rails to a physical chip. This
is the same class of hazard the identify feature's carrier rules exist to prevent, one layer down
and app-wide rather than per-screen.

It is latent today because the UI does not offer two long operations simultaneously in normal
flow — but the identify screen already demonstrated that a navigation path plus a worker's
lifetime can produce one, and the guard was easy to get wrong.

## Proposed fix

Serialize at the transport, not in each caller — a caller-side guard is what we just had to
retrofit once and would have to retrofit for every future screen.

- Add a module-level `threading.Lock` in `minigecko/core/minipro.py` held for the duration of
  `_run_subprocess` (both the blocking and streaming paths).
- Decide the contention policy deliberately and document it: block until free, or fail fast with
  a clear `MiniproResult(ok=False, stderr="programmer busy")`. Fail-fast is probably better for a
  TUI — a queued erase firing minutes later on a chip the user has since swapped is its own
  hazard.
- Consider a cross-process lock (a lockfile under `$XDG_RUNTIME_DIR`) as well: two MiniGecko
  instances, or MiniGecko alongside a hand-run `minipro`, hit the same device. In-process locking
  does nothing there.
- Then simplify the identify screen's local `_probing` flag if the transport guarantee makes it
  redundant for safety (it is still wanted for UI state).

## Done when

- Two threads calling any two `minipro` operations concurrently cannot have overlapping
  subprocesses; a test demonstrates the serialization (or the fail-fast result).
- The contention policy is documented in the module docstring.
- The identify screen's `_probing` flag is re-examined against the new guarantee.
- Decided (and recorded) whether cross-process locking is in scope now or a follow-up.


### MINIGECKO-009 — minipro transport: returncode is untrustworthy on early-return failure paths

**Priority:** high

Found while implementing MINIGECKO-005 (chip identifier Stage 1). The instance was fixed
defensively inside `read_chip_id`; this task fixes the class.

## The defect

`MiniproResult.returncode` is declared `returncode: int = 0` (`minigecko/core/minipro.py:37`).
`_run_subprocess` has five early-return failure paths that construct a result **without setting
it**, so it silently reads as a successful exit status:

- binary not found (`minipro.py:99-102`)
- `subprocess.run` timeout (`:116`)
- `OSError` on the non-streaming path (`:118`)
- `OSError` spawning the streaming path (`:129`)
- timeout on the streaming path (`:173`)

Any caller that treats `returncode` as an exit status can therefore conclude "the command
succeeded" from a command that never ran.

## Why it matters — the concrete near-miss

Stage 1's `read_chip_id` distinguishes "the socketed chip IS the carrier" from "we read a
different ID" partly on exit status, because `minipro -D` exits 1 on an ID mismatch and a
mismatch is that feature's success case. With `returncode` defaulting to 0, pointing the binary
path at a nonexistent file produced:

    read_chip_id('AM2764A@DIP28').data
    -> {'expected_id': None, 'chip_id': None, 'matched': True}

`matched=True` from a probe that never reached hardware. Downstream that becomes a `confirmed`
candidate, so the identify wizard would have reported "confirmed by silicon ID" on a machine
with **no programmer attached** — a fabricated confirmation, which for this feature is worse
than failing to identify at all.

`read_chip_id` now guards with `result.ok and result.returncode == 0`, so Stage 1 is safe. But
every other caller still reads a `returncode` that lies on those five paths, and the next one
written will not know to guard.

## Proposed fix

Set an explicit non-zero `returncode` on each early-return path in `_run_subprocess` — a
sentinel such as `-1` for "never ran / no exit status" reads clearly and is distinguishable from
any real minipro exit code. Then audit callers that branch on `returncode` and simplify any
that only guard because of this.

Consider also making `returncode` a required field (no default) so a future construction site
cannot omit it silently, or `returncode: int | None = None` so "no exit status" is
representable rather than aliased onto 0. Either is a small change with a compile-time-ish
benefit; the sentinel is the least invasive.

## Done when

- No `_run_subprocess` return path leaves `returncode` at an implicit 0 when the command did not
  run to completion.
- A test asserts that a missing binary yields a result whose `returncode` is not 0.
- `read_chip_id`'s defensive `result.ok and ...` guard is re-examined: keep it (belt and braces
  is fine here) but note in its docstring that the transport now reports honestly.
- Every existing caller that reads `returncode` is checked against the new semantics.


### MINIGECKO-008 — device_db: ambiguous device names silently resolve to one entry


Found while implementing MINIGECKO-005 (chip identifier Stage 1).

## The defect

`device_db._parse_infoic` indexes entries with `db[variant] = entry` in a loop, so when two
catalogue entries claim the same name, the last one parsed silently wins. `get_device(name)`
then returns that winner with no indication an alternative exists.

Concrete case: **`27C256@DIP28` is claimed by two entries** — a PHILIPS one that is NOT
chip-ID-capable, and a MICROCHIP one that IS (and is also DIP-28). `get_device` returns the
PHILIPS entry, so a caller asking "can this device report its silicon ID?" gets `False` for a
name that also denotes a device answering `True`.

Measured scope across the catalogue: **179 of 10152** entries have a `canonical_names[0]` that
resolves to a *different* entry. Zero entries have no name that resolves back to themselves.

## Why it matters beyond one lookup

Anything mapping a name back to an entry hits this: the identify wizard's results table, any
ranking or filtering by hardware flags, and the IC info panel. Stage 1 works around it inside
`identify.probe_carriers` via a private `_addressable_name(entry)` helper that picks a name
which both resolves back to the entry and carries a package consistent with it — but that is a
local patch over a shared-layer defect, and the next consumer will rediscover it.

The workaround also has real safety weight in the identify path: a naive first-resolving-name
rule produced `27C256@SOIC28` as a candidate carrier for a **DIP-28** socket, and a carrier
name is what `minipro -p` uses to decide which socket pins carry VCC and GND.

## Proposed fix

Add `get_devices(name) -> list[dict]` to `minigecko/core/device_db.py` returning every entry
claiming the name, keeping `get_device` as the single-result convenience wrapper (documented as
"first match; use get_devices when ambiguity matters"). Build a secondary
`dict[str, list[dict]]` index alongside the existing one rather than changing its type, so no
current caller changes behaviour.

Then reconsider whether `identify._addressable_name` should be expressed in terms of
`get_devices`, and whether the UI should disambiguate by manufacturer when a name is claimed
more than once.

## Done when

- `get_devices("27C256@DIP28")` returns both the PHILIPS and MICROCHIP entries.
- `get_device` behaviour is unchanged for every existing caller.
- A test pins the known-ambiguous name, and one asserts that every name in the index resolves
  to an entry that actually lists it in `canonical_names`.
- Documented in the module docstring: names are not unique keys.


### MINIGECKO-007 — Chip identifier Stage 3 — memory capacity profiling

**Priority:** low

Depends on MINIGECKO-005 (Stage 1). Design context: vault note
`projects/minigecko/chip-identifier-design-faint-marking-ic-identification.md`.

SRAM, mask ROM, and older 27C EPROMs have no chip ID. They can be characterised
by capacity and behaviour rather than identified by name:

- SRAM: pattern write + readback to find where the address space wraps, giving
  capacity. Destructive to SRAM *contents* only, which is acceptable — but this
  is the one stage that writes, so it needs a hard confirmation and must never
  run against a chip that might be ROM.
- Mask ROM / EPROM: read and fingerprint. Capacity from address wrap-around;
  possible content-hash matching against known dumps.

Realistic output is "DIP-28, 32Kx8, behaves like a 27C256" — a family and size,
rarely an exact part number. The UI must be honest about that.

Not designed in detail yet — needs its own brainstorming pass. The write-enabled
nature of the SRAM probe makes its safety model materially different from Stages
1-2, so do not fold it in casually.


### MINIGECKO-006 — Chip identifier Stage 2 — logic vector sweep

**Priority:** low

Depends on MINIGECKO-005 (Stage 1). Design context: vault note
`projects/minigecko/chip-identifier-design-faint-marking-ic-identification.md`.

74xx/40xx logic ICs carry no chip ID, so Stage 1's silicon probe cannot see
them. They can only be identified behaviourally: run `minipro -p <candidate> -T`
against each of the 261 `logicic.xml` entries whose `pin_count` matches, and
report which pass.

Notes carried over from the Stage 1 design:

- The logic candidate pool comes from `logicdb` / the `pin_count` field, NOT the
  package filter — logic entries have empty package strings.
- Must be a cancellable background worker with a live-filling results table; the
  sweep is minutes, not seconds.
- Strictly opt-in, launched from Stage 1's `suggested_next` offers with an
  estimated duration shown up front.
- Same pin-count and pin-contact guardrails as Stage 1.

Not designed in detail yet — needs its own brainstorming pass before planning.


### MINIGECKO-005 — Chip identifier Stage 1 — identify core + wizard


Identify a DIP IC whose top markings are too faint to read, without damaging it.

**Implementation plan:** `docs/superpowers/plans/2026-08-17-chip-identifier-stage1.md`
in the minigecko repo — 10 TDD tasks with full test and implementation code.
Kept in-repo rather than in the vault because executing agents tick its
checkboxes as they go; this task is its tracker.

**Design:** vault notes
- `projects/minigecko/chip-identifier-design-faint-marking-ic-identification.md`
- `projects/minigecko/chip-identifier-hardware-verified-minipro-behaviour.md`

## Scope

Stage 1 of three. The fast, safe tier only; the slow sweeps are MINIGECKO-006
and MINIGECKO-007 and are merely *offered* here, greyed out.

New files:

- `minigecko/core/identify.py` — engine. `ChipHint` / `Evidence` / `Candidate` /
  `IdentifyReport` / `NextStep`; helpers `parse_package`, `socket_pins`,
  `chip_id_index`, `probe_carriers`, `socket_width`; entry point
  `identify(hint, probe=None) -> IdentifyReport`.
- `minigecko/ui/modals/identify.py` — `IdentifyScreen`, a 3-step `ModalScreen`
  wizard (input -> safety confirm -> results).

Also modified: `core/minipro.py` (new `read_chip_id`, `parse_bad_pins`;
`pin_check_device` gains `data["bad_pins"]`), `core/emulator.py` (`-D` branch),
`core/__init__.py`, `ui/modals/__init__.py`, `ui/app_shell.py` (`i` keybinding).

## Key mechanism

`minipro -p <carrier> -D` reads the chip ID and nothing else. A *probe carrier*
is any ID-capable, non-ISP DIP device whose resolved socket pin count exactly
equals the user's stated pin count, used purely as an electrical harness.
Reverse-index the `chip_id` values already parsed in `device_db.py` to map
observed ID -> candidate devices, then intersect with the catalogue filter.

## Non-negotiables

- Read-only by construction: only `-D` and `-z`. No `-w`, `-E`, `-m`. The probe
  callable takes no payload, so no call shape can write to a chip.
- **`minipro -D` exits 1 on ID mismatch, and mismatch is the SUCCESS case.**
  Never gate ID parsing on `result.ok`. Verified on real hardware.
- All minipro output is on stderr; stdout is empty. Parse both concatenated.
- `probe=None` means tier 0 only — the engine cannot energize the socket unless
  a probe is passed explicitly. (Deliberate change from the design note, which
  had it default to the real hardware call.)
- Probe carriers must match pin count *exactly* — excluded, not down-ranked.
- `minipro -z` pin-contact check must pass before anything energizes.
- Explicit user confirmation before the first probe, naming VCC and pin-1
  orientation.
- Use the `has_chip_id` flag as the authority for ID capability, not
  `chip_id != 0`.
- Resolve pin count from the package string FIRST, `pin_count` field second.
  The field is scrambled for non-DIP parts (33 means BGA48, 34 means BGA63,
  63 means PLCC32) and is only trustworthy when the package string is empty.

## Done when

- `identify()` returns a ranked `IdentifyReport` for a DIP hint, with per-
  candidate evidence explaining each suggestion.
- Wizard reachable from the TUI on `i`; result selection leaves the app in the
  same state as a manual chip selection.
- Tier 0 works with no programmer attached and is labelled as such.
- Diagnostics (not exceptions) for: no programmer, no carrier, pin-contact
  failure, all-zero or all-FF ID, unknown ID, empty candidate set, probe
  exception.
- Tests in `tests/test_core.py` all green in CI with no hardware.
- Post-implementation hardware check: capture what minipro prints when the chip
  ID actually MATCHES the carrier (unobserved so far — verification was done on
  an empty socket) and update the hardware-verified note.


### MINIGECKO-003 — PLD editor panel


**Depends on:** MINIGECKO-001, MINIGECKO-002

**Goal:** Replace the stub in `tab-cupl` with a working PLD editor that can open
a `.pld` file, compile it with openCUPL, and optionally program the result —
all in one workflow.

**Scope:**

New file: `minigecko/ui/cupl_panel.py` — a `CuplPanel(Widget)` with this layout:

```
┌──────────────────────────────────────────┐
│ [Open .pld]          design: <name>      │  ← toolbar row (Horizontal)
├──────────────────────────────────────────┤
│                                          │
│  TextArea  (PLD source, editable)        │
│                                          │
├──────────────────────────────────────────┤
│  RichLog  (compile status / errors)      │
├──────────────────────────────────────────┤
│ [Compile]          [Compile & Program]   │  ← button row (Horizontal)
└──────────────────────────────────────────┘
```

Implementation details:
- "Open .pld" button: reuse the existing `FilePickerScreen` modal; load file
  text into the `TextArea`
- Device name: extract from `.pld` header with regex `Device\s+(\S+?)[\s;]`
  before calling `cupl_compile` — reuse the same string for both the compiler
  and `write_device()`
- "Compile" button: `@work(thread=True)` worker — calls `cupl_compile(source,
  design_name)`, writes JEDEC string to a `tempfile.NamedTemporaryFile`, logs
  success or exception to the `RichLog`
- "Compile & Program" button: same compile step, then calls
  `app.run_write_to_device_op(device_name, tmp_path)` — reuse the existing
  method from `app_shell.py`
- Log format follows existing convention:
  `[green]COMPILE  OK[/]  <design>  GAL22V10`
  `[red]COMPILE  FAILED:[/]  <error message>`
- `CuplPanel` is mounted in `app_shell.py` inside `tab-cupl` replacing the stub

**Note:** `cupl_compile` may raise `ValueError` (unknown device, fuse overflow)
or any exception from Espresso failing. Catch all exceptions in the worker and
log them to the `RichLog` — never let a compile error crash the app.

**Done when:**
- [ ] Opening a `.pld` file populates the `TextArea`
- [ ] "Compile" on a valid `.pld` logs success and produces a JEDEC tempfile
- [ ] "Compile" on an invalid `.pld` logs the error cleanly; app keeps running
- [ ] "Compile & Program" with a GAL22V10 seated calls `write_device` and logs result
- [ ] Device name is extracted from the `.pld` header, not entered manually
- [ ] No existing programmer-tab functionality regresses

### MINIGECKO-001 — Drop in generated openCUPL module


### MINIGECKO-001 — Drop in generated openCUPL module

**Status:** `ready`
**Depends on:** nothing

**Goal:** Make `from minigecko.compiler import cupl_compile` work so later tasks
can call the compiler without subprocess spawning or `sys.path` hacks.

**Scope:**
- Run `pync compile --target python src/openCUPL.pync` and collect the generated
  `openCUPL.py` (and any sibling generated files it imports)
- Create `minigecko/compiler/` package directory
- Copy generated file(s) into `minigecko/compiler/`
- Add `minigecko/compiler/__init__.py` with a single clean re-export:
  `from .openCUPL import compile as cupl_compile`
- Verify in a Python REPL: `from minigecko.compiler import cupl_compile` succeeds
- Add `espresso` to the README prerequisites section (must be on PATH at runtime)
- Commit the generated file — CI does not need `pync`

**Note:** Do not modify any generated file. If the generated output has import
dependencies on other generated modules, copy all of them as-is into
`minigecko/compiler/`. Treat the generated directory as read-only upstream source.

**Done when:**
- [ ] `minigecko/compiler/__init__.py` exists and exports `cupl_compile`
- [ ] `python -c "from minigecko.compiler import cupl_compile; print('ok')"` exits 0
- [ ] README lists `espresso` as a prerequisite
- [ ] No existing tests regress

---

## Completed

### MINIGECKO-004 — Help load optimization

**Priority:** low

Speed up help loading with cache and add 'loading' message...

**Completed:** 2026-04-02

### MINIGECKO-002 — Tab chrome refactor


**Depends on:** nothing (independent of MINIGECKO-001)

**Goal:** Restructure `app_shell.py` so the main body lives inside a
`TabbedContent` with two tabs: **Programmer** (existing layout) and **openCUPL**
(stub). All existing behaviour must be unchanged.

**Scope:**
- Add `TabbedContent`, `TabPane` to imports in `app_shell.py`
- Wrap the existing `Horizontal(id="body")` block in
  `TabPane("Programmer", id="tab-programmer")`
- Add `TabPane("openCUPL", id="tab-cupl")` containing a single
  `Static("PLD editor — coming soon", id="cupl-stub")`
- Wrap both panes in `TabbedContent(id="main-tabs")`
- Verify all existing `query_one()` calls still resolve — Textual queries the
  full DOM including inactive tabs, so no changes should be needed
- Smoke test: switch tabs with mouse and keyboard; confirm programmer tab is
  fully functional after switching back

**Note:** Do not touch toolbar wiring, key bindings, worker methods, or modal
screens. Layout change only. The stub content in `tab-cupl` will be replaced
by MINIGECKO-003.

**Done when:**
- [ ] App launches with two visible tabs
- [ ] Switching to openCUPL tab shows the stub static
- [ ] Switching back to Programmer tab: IC select, IC ops, file open, hex panel,
      action log, and programmer detection all work as before
- [ ] No existing tests regress

**Completed:** 2026-03-28

---
