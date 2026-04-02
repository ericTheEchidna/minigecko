[Back to Table of Contents](toc.md)

## 4. Starting MiniGecko

### 4.1 Launching the TUI

You can launch the MiniGecko interface either directly or with the explicit
`tui` subcommand.

Default launch (recommended):

```bash
minigecko
```

Explicit launch:

```bash
minigecko tui
```

Both commands open the same Textual user interface.

Alternative launch form (module mode):

```bash
python -m minigecko
```

On successful startup, you should see the MiniGecko TUI with header, toolbar,
hex panel, IC information panel, and action log.

To exit the application, use `Ctrl+Q`.

### 4.2 Emulator Mode

Emulator mode lets you run MiniGecko without a physical programmer attached.
It is intended for UI testing, workflow rehearsal, and development.

Enable emulator mode:

```bash
MINIGECKO_EMULATE=1 minigecko
```

What emulator mode does:

- Replaces the real `minipro` transport with a simulated backend.
- Reports a detected programmer so the application can start normally.
- Provides a small built-in list of example devices for selection and testing.
- Simulates core operations including read, write, verify, erase, blank check,
	pin check, and RAM or logic test.

What to expect:

- Read operations return generated or fixture-based data rather than real chip
	contents.
- Most emulated operations report success so you can exercise the full UI flow.
- Blank check may intentionally fail for fixture-backed devices to simulate a
	non-blank part.

Limitations:

- Emulator mode does not communicate with real hardware.
- Results are suitable for workflow testing, not hardware validation.
- Device coverage is intentionally limited and does not represent the full
	`minipro` database.
- Timing, electrical behavior, and hardware-specific failures are not modeled.
