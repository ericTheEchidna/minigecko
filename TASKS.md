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
