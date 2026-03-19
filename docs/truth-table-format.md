# Truth Table Format

> **Status: planned / not yet implemented.**
> Logic IC testing currently delegates entirely to minipro's built-in test
> vectors (`minipro -p <device> -T`). A custom YAML truth table system is
> planned for chips not covered by minipro's database.

MiniGecko truth tables will be YAML files in `data/truth_tables/`, one file per part family.

---

## Full schema

```yaml
# ── Metadata ────────────────────────────────────────────────────────────────
meta:
  part: 74HCT138                     # canonical part number (becomes the filename stem)
  description: "Short description"   # one line, shown in list-parts output
  package: DIP-16                    # primary test package
  datasheet: "https://…"             # primary datasheet URL (optional)
  families:                          # compatible parts that share this truth table
    - 74HCT138
    - 74LS138
    - 74HC138

# ── Pin map ──────────────────────────────────────────────────────────────────
inputs:
  - name: A0        # signal name used in truth_table columns
    pin: 1          # physical pin number (DIP numbering)
  - name: OE_n      # active-low convention: suffix _n
    pin: 4
    note: "active-low enable"   # optional, appears in TUI tooltip

outputs:
  - name: Y0
    pin: 15
    active: low     # 'low' or 'high'; affects how the engine interprets assertion

# ── Truth table ──────────────────────────────────────────────────────────────
truth_table:
  columns:
    inputs:  [A0, A1, OE_n]     # must match input name list above
    outputs: [Y0, Y1, Y2]       # must match output name list above
  rows:
    # Each row: input values first, then output values, then optional comment
    - [0, 0, 0,   1, 0, 0]   # comment here is stripped by parser
    - [0, 1, 0,   0, 1, 0]
    - [1, 0, 0,   0, 0, 1]
    - [0, 0, 1,   1, 1, 1]   # OE_n=1 → all deasserted

# ── Optional: test strategy hint ─────────────────────────────────────────────
# Tells TestEngine how to handle chips that need sequenced stimulus
# (latches, registers) vs. pure combinational chips (no hint needed).
test_strategy: "latch_sequence"
# Valid values:
#   combinational   (default) — exhaustive input sweep
#   per_bit_sweep   — drive each data bit independently (transceiver, buffer)
#   latch_sequence  — transparent + hold sequence (latch, register)
```

---

## Special values

| Value | Meaning |
|---|---|
| `0` | Logic low |
| `1` | Logic high |
| `X` | Don't-care (input); output not checked |
| `Z` | High-impedance output (3-state) |
| `"prev"` | Output holds previous value (latched) |

---

## Conventions

### Active-low signals
Use `_n` suffix for active-low pins: `OE_n`, `CE_n`, `WE_n`, `E1_n`.
The truth table rows use the raw logic level on the pin (0 = asserted for active-low).

### Power pins
Do not include Vcc or GND in inputs/outputs. They are implicit.

### Multiple packages
List the primary DIP package. If the pin map is significantly different in
a surface-mount variant, create a separate file (e.g. `74HCT138-SOIC.yaml`).

### Comments
Inline comments after the row values are valid YAML but are stripped by
the parser. Use them freely to document which input combination is being tested.

---

## Validation

```bash
# Check all bundled truth tables parse without error
python -c "
from minigecko.core.logicdb import list_logic_ics
ics = list_logic_ics()
print(f'Loaded {len(ics)} logic IC entries')
for ic in ics[:10]:
  print(f'{ic.name:20} {ic.pins:2} pins  {ic.vector_count:3} vectors')
"
```

---

## Naming

| Part family | File |
|---|---|
| 74HCT138 (and LS/HC variants) | `74HCT138.yaml` |
| 74HCT245 | `74HCT245.yaml` |
| 27C256 EPROM | `27C256.yaml` |
| AT28C256 EEPROM | `AT28C256.yaml` |

Use the most common HCT or HC part number as the canonical name.
