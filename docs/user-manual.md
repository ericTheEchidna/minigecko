# MiniGecko User Manual

Draft status: skeleton

This document is the long-form end-user manual for MiniGecko.

## 1. About This Manual

### 1.1 Audience

This manual is written for people who use MiniGecko to program, read, verify,
erase, and test integrated circuits with minipro-compatible hardware.

## 2. What MiniGecko Is

### 2.1 Overview

MiniGecko is a terminal UI for chip programming operations powered by minipro.

### 2.2 Hardware and Software Prerequisites

Before using MiniGecko, confirm the following prerequisites.

Hardware:

- A `minipro`-compatible programmer connected by USB.
- Commonly used supported families include TL866II+, T48, T56, and T76
	(plus other devices supported by your installed `minipro` build).
- A target IC that exists in the `minipro` device database.

Operating system:

- Linux environment (Ubuntu is tested; other distributions are expected to
	work when `minipro` is available).

Runtime and tools:

- Python 3.11 or newer.
- `minipro` installed and available on your `PATH`.
- Terminal support suitable for Textual applications (for example modern
	terminal emulators with standard keyboard and color support).

Optional but recommended:

- Permission to access USB devices for your user account (for example via
	appropriate `udev` rules, depending on your distro setup).
- A known-good binary file for write or compare workflows.

Quick preflight check:

```bash
python3 --version
minipro --version
```

## 3. Installation and Setup

### 3.1 Install minipro

MiniGecko depends on `minipro` for all programmer communication, so install
and verify `minipro` before installing MiniGecko.

Debian or Ubuntu:

```bash
sudo apt update
sudo apt install minipro
```

Arch Linux:

```bash
sudo pacman -Syu minipro
```

Build from source (if your distro package is unavailable or outdated):

```bash
git clone https://gitlab.com/DavidGriffith/minipro
cd minipro
make
sudo make install
```

Verify the install:

```bash
minipro --version
```

You should see version output and, when hardware is connected, a line like
`Found TL866II+ firmware 04.2.132`.

### 3.2 Install MiniGecko

After `minipro` is installed, clone the repository and install MiniGecko.

Standard install:

```bash
git clone https://github.com/ericTheEchidna/minigecko
cd minigecko
pip install -e .
```

Install with development extras (recommended if you plan to run tests or
contribute):

```bash
git clone https://github.com/ericTheEchidna/minigecko
cd minigecko
pip install -e ".[dev]"
```

This installs the `minigecko` CLI entry point into your active Python
environment.

### 3.3 Verify Installation

Run the following checks after installation:

```bash
minigecko version
minigecko detect
```

Expected behavior:

- `minigecko version` prints the installed MiniGecko version.
- `minigecko detect` reports programmer detection status.
	If hardware is connected and recognized, it should print an OK-style line
	with model and firmware information.

Optional no-hardware validation (emulator mode):

```bash
MINIGECKO_EMULATE=1 minigecko detect
```

This should report a detected emulated programmer and confirms MiniGecko can
start without physical hardware.

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

## 5. Interface Tour

### 5.1 Layout Overview

MiniGecko uses a multi-panel terminal layout designed around the most common
chip-programming workflow: select a device, inspect file contents, run an
operation, and review status.

Main screen structure:

- Header at the top, showing the application title and clock.
- Toolbar directly below the header, containing the chip-selection and IC
	operations controls.
- Hex panel on the left, used to display the currently loaded data buffer.
- IC information panel on the upper right, showing details for the selected
	device.
- Action log panel on the lower right, showing status messages and progress.
- Footer at the bottom, showing available key bindings.

Layout behavior:

- The left hex panel is wider than the right-side information area by default.
- The right side is split vertically into an information panel above and an
	action log below.
- The divider between left and right panels can be resized.
- The divider between the IC information panel and the action log can also be
	resized.
- Panel size changes are saved and restored between sessions.

Typical workflow on screen:

1. Select a chip from the toolbar.
2. Open or read data into the hex panel.
3. Review chip metadata in the IC information panel.
4. Run operations and monitor results in the action log.

### 5.2 Toolbar

The toolbar is the main control strip at the top of the application. It gives
you direct access to device selection and chip-specific operations.

Toolbar controls:

- `Selected IC: —` opens the chip selector.
- `IC Ops [d]` opens the operations menu for the currently selected device.

Behavior:

- On startup, no chip is selected, so the toolbar shows `Selected IC: —`.
- The `IC Ops` control is disabled until you choose a chip.
- After selection, the chip button updates to show the selected part name.
- Once a chip is selected, the `IC Ops` control becomes active.

How to use it:

- Click `Selected IC: —` or press `s` to open device selection.
- After selecting a device, click `IC Ops [d]` or press `d` to open the
	available actions for that chip.

The toolbar works together with the subtitle and action log: programmer status
is shown in the application subtitle, while operation results appear in the
action log panel.

### 5.3 Hex Panel

The hex panel shows the contents of the currently loaded file or the most
recent data read from a device.

What appears in the panel:

- One row per 16 bytes of data.
- A hexadecimal offset at the start of each row.
- Hex byte values in the middle columns.
- An ASCII preview at the right side of each row.

Display behavior:

- The panel header and offset input appear only after data has been loaded.
- `0x00` bytes are dimmed.
- `0xFF` bytes are highlighted distinctly.
- Printable ASCII characters are shown in the ASCII column; non-printable
	bytes are shown as `.`.

Navigation:

- Scroll through the panel normally using your terminal and Textual scrolling
	behavior.
- Use the offset input at the top of the panel to jump directly to a location.
- Enter offsets in hexadecimal, with or without a `0x` prefix.

Loading behavior:

- Opening a file replaces the current hex display with the new file contents.
- Reading from a device also updates the panel with the retrieved data.
- After loading, the view resets to the top of the buffer.

Display limit:

- The hex preview is capped at 10 MB for usability.
- If a file is larger than that limit, MiniGecko shows only the first portion
	and appends a truncation notice.

### 5.4 IC Info Panel

The IC information panel shows metadata for the currently selected device and
helps you confirm that you picked the correct part before running operations.

What it shows:

- The selected chip name.
- A summary line that may include chip type, memory size, package, pin count,
  and ISP capability.
- A decoded flag table derived from the `minipro` device database.
- A datasheet search link for the selected part.

Typical metadata fields:

- Device family or type, such as ROM, EEPROM, Flash, MCU, PLD, SRAM, Logic,
  NAND, or eMMC.
- Reported code-memory size.
- Package name, when available.
- Pin count.
- ISP support indicator, when applicable.

Decoded capability flags may include:

- Whether the device is erasable.
- Whether chip ID support exists.
- Whether the part uses 16-bit words.
- Whether data offset handling is present.
- Whether write-protect sequencing is required.
- Whether lock-bit or calibration support exists.
- Whether pin order is reversed.
- Whether adjustable VCC or VPP is indicated.
- Which programming interface type is reported.

Use this panel as a verification step before write or erase operations. If the
package, size, or capability flags do not match your actual device, return to
chip selection and choose the correct part.

### 5.5 Action Log Panel

The action log panel records application activity and is the main place to
confirm whether an operation succeeded, failed, or is still in progress.

What it shows:

- Timestamped log entries for major application events.
- File-open events.
- Programmer detection status.
- Chip-selection changes.
- Results of read, write, erase, compare, blank-check, pin-check, and logic
	test operations.

Log behavior:

- Each entry is prefixed with a time stamp in `HH:MM:SS` format.
- New entries automatically scroll into view.
- The panel reflows its contents when the terminal is resized.

Progress bar behavior:

- A progress bar appears during long-running operations when progress data is
	available.
- The bar shows percentage completion.
- When the operation finishes, the progress bar is hidden and reset.

How to use it:

- Watch the log while an operation is running rather than relying on the hex
	panel alone.
- Use it to distinguish between warnings, successful completion, and failures.
- If an operation fails, the most useful error text will usually appear here
	first.

## 6. Keyboard Shortcuts

MiniGecko provides application-wide shortcuts plus context-specific keys inside
modal dialogs.

Global shortcuts:

| Key | Action |
| --- | --- |
| `f` | Open the file picker |
| `s` | Open chip selection |
| `d` | Open IC operations for the selected chip |
| `v` | Tools action |
| `h` | Help action |
| `Ctrl+D` | Toggle theme |
| `Ctrl+Q` | Quit MiniGecko |
| `Ctrl+P` | Open the command palette |

Notes:

- `d` only works after a chip has been selected.
- `v` and `h` are bound at the application level, but their practical value
	depends on the current implementation behind those actions.

Chip selection dialog:

| Key | Action |
| --- | --- |
| `Enter` | Select the highlighted device |
| `Escape` | Cancel and close the dialog |

File picker dialog:

| Key | Action |
| --- | --- |
| `Enter` | Confirm the selected file |
| `Escape` | Cancel and close the dialog |

IC operations dialog:

| Key | Action |
| --- | --- |
| `Escape` | Close the operations dialog |

Write confirmation dialog:

| Key | Action |
| --- | --- |
| `Enter` | Confirm the write |
| `Escape` | Cancel |
| `Space` | Toggle the verify-after-write checkbox |

Erase confirmation dialog:

| Key | Action |
| --- | --- |
| `Enter` | Confirm the erase |
| `Escape` | Cancel |
| `Space` | Toggle the selected checkbox |

Hex view modal:

| Key | Action |
| --- | --- |
| `Escape` | Close the hex view |
| `Up` / `Down` | Scroll one step |
| `PgUp` / `PgDn` | Scroll one page |
| `Home` | Jump to the top |
| `End` | Jump to the bottom |

## 7. Chip Selection

### 7.1 Opening the Chip Selector

Before you can run most device operations, you must select the correct chip.

Ways to open the chip selector:

- Click the `Selected IC: —` control in the toolbar.
- Press `s` from the main application screen.

What happens when it opens:

- MiniGecko displays a modal selection dialog over the main interface.
- The dialog loads device names from the `minipro` database.
- Focus starts in the search input so you can type immediately.
- The status line shows how many devices are available or matched.

Why this step matters:

- The selected chip determines which operations are enabled.
- The IC information panel is populated from the selected part.
- The `IC Ops` control remains disabled until a chip is chosen.

### 7.2 Filtering and Search

The chip selector is designed to narrow a large device database quickly.

Category filters:

- `All`
- `ROM / EEPROM / Flash`
- `MCU`
- `PLD`
- `SRAM`
- `Logic`
- `NAND`
- `eMMC`
- `VGA`

Search behavior:

- Type directly into the search box to filter results live.
- Matching is case-insensitive.
- Matching is based on substring search against the device name.
- If no search text is entered, the list shows all devices in the active
	category.

Result display:

- The result list updates immediately as you type.
- The status line shows how many devices match the current filter.
- If there are many matches, MiniGecko shows only the first 200 results.
- When results are truncated, the status line indicates how many are shown
	versus how many total matches exist.

Recommended workflow:

1. Choose the broad device category first if you know it.
2. Type part of the chip name, such as a family or exact part number.
3. Review the remaining matches before confirming selection.

### 7.3 Selecting a Device

After narrowing the list, confirm the correct device from the visible results.

Ways to select a device:

- Highlight a device in the list and press `Enter`.
- Double-click the same device entry to select it immediately.

After selection:

- The chip selector closes.
- The toolbar updates from `Selected IC: —` to the chosen part name.
- The `IC Ops` control becomes active.
- The IC information panel refreshes with metadata for the selected device.
- The action log records the chip selection event.

If you cancel instead:

- The dialog closes without changing the current selection.
- `IC Ops` remains disabled if no device had been selected previously.

Best practice:

- Confirm the full part number, package variant, and relevant capabilities in
	the IC information panel before using write or erase operations.

## 8. File Operations

### 8.1 Opening a File

TODO: Document file picker usage and navigation.

### 8.2 Saving to a File

TODO: Document write-to-file workflow.

### 8.3 Data Display Limits

TODO: Document max display size and truncation notes.

## 9. Device Operations

### 9.1 Read from Device

TODO: Describe flow, outputs, and common warnings.

### 9.2 Write to Device

TODO: Describe confirmation, safety checks, and verify-after-write.

### 9.3 Blank Check

TODO: Explain pass/fail meaning.

### 9.4 Erase

TODO: Explain electrical erase vs UV-only devices.

### 9.5 Compare vs File

TODO: Explain comparison output and mismatch reporting.

### 9.6 RAM or Logic Test

TODO: Explain supported devices and result interpretation.

### 9.7 Pin Check

TODO: Explain contact failures and troubleshooting tips.

## 10. Safety and Best Practices

### 10.1 Before You Program

TODO: Add checklist for voltage, orientation, and part ID confirmation.

### 10.2 Destructive Operations

TODO: Add backup-first guidance for erase/write operations.

### 10.3 Verification Strategy

TODO: Recommend verify and compare routines.

## 11. Configuration and Persistence

### 11.1 State File

TODO: Document state file location and stored fields.

### 11.2 Environment Variables

TODO: Document MINIGECKO_EMULATE and MINIPRO_HOME.

### 11.3 Custom minipro Path

TODO: Explain how minipro path override is set and used.

## 12. Troubleshooting

### 12.1 Programmer Not Detected

TODO: Add USB permissions, cable, power, and command checks.

### 12.2 Operation Fails Midway

TODO: Add guidance for unstable contacts, chip mismatch, and retries.

### 12.3 Device Not in Database

TODO: Add minipro DB update and fallback guidance.

### 12.4 UI Issues

TODO: Add terminal compatibility and resize behavior notes.

## 13. Glossary

TODO: Define terms (ZIF, ISP, blank check, verify, VPP, VCC).

## 14. Quick Reference

TODO: One-page command and shortcut cheat sheet.

## 15. Revision History

| Version | Date | Notes |
| --- | --- | --- |
| 0.1 | 2026-03-19 | Initial skeleton |

## Appendix A: Fill Progress Checklist

- [ ] About This Manual
- [ ] What MiniGecko Is
- [ ] Installation and Setup
- [ ] Starting MiniGecko
- [ ] Interface Tour
- [ ] Keyboard Shortcuts
- [ ] Chip Selection
- [ ] File Operations
- [ ] Device Operations
- [ ] Safety and Best Practices
- [ ] Configuration and Persistence
- [ ] Troubleshooting
- [ ] Glossary
- [ ] Quick Reference