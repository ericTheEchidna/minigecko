# MiniGecko

**Open source TUI programmer suite powered by [minipro](https://gitlab.com/DavidGriffith/minipro).**

MiniGecko wraps the `minipro` CLI in a polished terminal UI. It should work with any programmer that minipro
supports — TL866II+, T48, T56, T76, and others.

> **Early days.** This is a personal tool that grew into something shareable.
> It works well for the author's use cases but is not battle-tested at scale.
> Bug reports and contributions are very welcome.

---

## What it does

- **IC selector** with live search across minipro's full device database
- **Device info panel** — chip type, size, package, and all hardware flags
  decoded from minipro's XML database (erasable, chip ID, write-protect
  sequencing, programming interface, etc.)
- **Operations** filtered by chip type: read, write (with confirmation),
  verify, erase, blank check, compare, logic test, pin check
- **Real-time progress bar** streamed from minipro's stderr during long operations
- **Action log** with timestamps and colour-coded results
- **UV EPROM awareness** — chips that require UV erase (27C-series) are
  flagged in the UI; the Erase operation is disabled with an explanation
- **Emulator mode** (`MINIGECKO_EMULATE=1`) for offline development without hardware

---

## Requirements

- Linux (tested on Ubuntu; other distros should work)
- Python >= 3.11
- [`minipro`](https://gitlab.com/DavidGriffith/minipro) on `PATH`
- A supported programmer (TL866II+, T48, T56, T76, ...)

```bash
# Debian / Ubuntu
sudo apt install minipro

# From source
git clone https://gitlab.com/DavidGriffith/minipro
cd minipro && make && sudo make install
```

---

## Installation

```bash
git clone https://github.com/ericTheEchidna/minigecko
cd minigecko
pip install -e ".[dev]"
```

---

## Usage

### TUI

```bash
minigecko          # launches the interactive TUI
minigecko tui      # explicit
```

### Emulator mode (no hardware needed)

```bash
MINIGECKO_EMULATE=1 minigecko
```

---

## Architecture

```
minigecko/
├── core/
│   ├── minipro.py      # minipro CLI bridge; transport is swappable
│   ├── device_db.py    # parses infoic.xml + logicic.xml; decodes flags
│   └── emulator.py     # fake transport for offline development
├── app.py              # Textual TUI
└── __main__.py         # Click CLI entry point

data/
└── test_pattern.bin    # 32 KB address-pattern binary for write testing
```

The core layer is transport-swappable: when direct `libminipro` bindings
become available they can replace the subprocess bridge without touching
anything above `core/minipro.py`.

---

## Roadmap

- [ ] Hex editor / diff view for read buffers
- [ ] Device auto-detect from chip ID
- [ ] Hardware hotplug via `udev` instead of polling timer
- [ ] `libminipro` Python bindings (direct USB, no subprocess)
- [ ] Windows support (would require libminipro bindings or a port of minipro)
- [ ] in development: richer chip descriptions

---

## Background

MiniGecko started as a personal tool built while working on **Forbin80** — a
homebrew Z80 SBC. Sourcing cheap no-name 74-series logic and needing to
program EEPROMs repeatedly made a reliable, open-source, TUI chip tool a
practical necessity.

**[Ben Eater](https://eater.net)'s videos** were a direct inspiration for
this project — his patient, thorough approach to explaining digital logic
and homebrew computing is what got the author deep enough into this hobby
to need a tool like MiniGecko in the first place. If you haven't watched his
series on building an 8-bit computer from scratch or the 6502 project, you REALLY should.

---

## A note on AI assistance

This project was built with significant help from
[Claude Code](https://claude.ai/claude-code) (Anthropic's AI coding
assistant). Claude wrote substantial portions of the code, helped debug
hardware quirks, and co-authored most commits.

The architecture decisions, hardware domain knowledge, and direction are
human — the implementation often wasn't. This is disclosed openly because
we think that's the honest thing to do.

---

## Contributing

Found a bug or have a question? [Open an issue](https://github.com/ericTheEchidna/minigecko/issues).

See [CONTRIBUTING.md](CONTRIBUTING.md) for code contributions.

---

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

minipro itself is also GPL-3.0. The device databases (`infoic.xml`,
`logicic.xml`) are part of the minipro project and distributed under the
same license.
