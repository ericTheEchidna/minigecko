# Contributing to MiniGecko

## Ways to contribute

- **Bug reports** — open an issue with `minigecko version` output and the
  exact steps to reproduce. Include the minipro version (`minipro --version`)
  and the chip you were working with.

- **Hardware testing** — try minigecko with a programmer or chip type not yet
  confirmed to work and report results, even if everything is fine.

- **Core improvements** — especially: `libminipro` Python bindings,
  `udev` hotplug detection, JEDEC/GAL fuse map support.



## Code contributions

### Setup

```bash
git clone https://github.com/ericTheEchidna/minigecko
cd minigecko
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Emulator mode

You don't need hardware to work on the UI or core logic:

```bash
MINIGECKO_EMULATE=1 minigecko
```

### Tests

```bash
pytest
```

All PRs must pass `pytest` with no new failures.

### Style

- PEP 8, type hints on all public functions.
- No new runtime dependencies without discussion first.
- No line longer than 100 characters.

### Commit messages

```
<scope>: <short imperative summary>

Optional longer explanation. Wrap at 72 chars.
```

Scopes: `core`, `app`, `cli`, `tests`, `docs`, `ci`.

---

## License

By submitting a PR you agree your contribution will be licensed under GPL-3.0-or-later.
