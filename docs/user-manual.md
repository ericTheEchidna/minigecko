# MiniGecko User Manual

Draft status: complete

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
`Found TL866II+ 04.2.132`.

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
| `Left` / `Right` | Cycle through chip type categories (when search box is empty) |
| `Up` / `Down` | Move between results (works from the search input) |
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
| `Up` / `Down` | Move between operations |
| `Enter` | Activate highlighted operation |
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

Use the file picker to load an existing binary file into the hex panel.

Ways to open the file picker:

- Press `f` from the main screen.

File picker behavior:

- The picker opens as a modal dialog over the main interface.
- It starts in the last directory you used, or your home directory if no
	previous location has been saved.
- The current directory is shown as a navigable tree.
- The `↑ ..` control moves up to the parent directory.

How to choose a file:

- Select a file in the directory tree and press `Enter`.
- Double-click a file to open it immediately.
- Press `Escape` to cancel without loading anything.

After a file is opened:

- MiniGecko remembers that file's parent directory for next time.
- The application subtitle updates to include the file path.
- The action log records the opened filename and size.
- The hex panel refreshes to show the file contents.

### 8.2 Saving to a File

The write-to-file operation saves the current in-memory data to a file you
choose. It is available from the IC operations menu as `Write to file`.

Preconditions:

- Data must be loaded, either from a file you opened or from a previous device
  read operation.
- If no data is loaded, MiniGecko logs a warning and the operation does nothing.

Workflow:

1. Open the IC operations menu with `d` or by clicking `IC Ops`.
2. Click `Write to file`.
3. The file picker opens. Navigate to the target directory and select a
   destination path.
4. Confirm with `Enter`.

After saving:

- The action log records the save event with the destination filename.
- The application subtitle updates to reflect the new file path.
- The saved file becomes the new active data source.

### 8.3 Data Display Limits

The hex panel renders binary data in memory and has a practical display cap.

- Files larger than 10 MB are truncated for display purposes only.
- When truncation occurs, MiniGecko shows the first 10 MB of the file in the
  hex panel and appends a notice at the end of the visible content.
- The full, unmodified file is still used as the write source for device
  operations and file save operations.
- The truncation only affects what is visible — it does not alter file contents
  or affect write accuracy.

## 9. Device Operations

### 9.1 Read from Device

Reads the entire contents of the selected chip into a temporary file, then
loads the data into the hex panel.

Workflow:

1. Select a chip and open `IC Ops`.
2. Click `Read from device`.
3. A progress bar shows streaming percentage while the read operation runs.
4. On success, the action log reports the byte count and the hex panel updates.

Warnings:

- If `minipro` detects a chip ID mismatch, MiniGecko logs a warning but
  proceeds with the read. Review the IC information panel to confirm you have
  the correct part selected before proceeding.
- On failure, the action log shows the raw error from `minipro`.

### 9.2 Write to Device

Writes the current in-memory data buffer to the selected chip.

DESTRUCTIVE ACTION: This permanently overwrites the device contents.

Preconditions:

- Data must be loaded from a file or a previous read operation.
- If no data is loaded, MiniGecko logs a warning and cancels the operation.

Workflow:

1. Load or read the data you want to write.
2. Open `IC Ops` and click `Write to device`.
3. A confirmation dialog appears showing the data source name and a warning.
4. Optionally toggle the `Verify after write` checkbox (enabled by default).
5. Press `Enter` to confirm or `Escape` to cancel.
6. A progress bar shows streaming percentage while the write runs.
7. If verify is enabled, MiniGecko reads the device back and compares it
   against the written file. The log reports how many bytes match.

NOTE: Verify after write reads the device a second time and performs a
byte-by-byte comparison. A mismatch is reported with a byte count and
percentage.

### 9.3 Blank Check

Verifies that every byte in the selected device reads as `0xFF`, indicating
the chip is in a fully erased state.

Workflow:

1. Open `IC Ops` and click `Blank Check`.
2. `minipro` checks the device contents.
3. The action log reports pass or fail.

Result interpretation:

- Pass (`all 0xFF`): the device is blank and ready to program.
- Fail (`not blank`): the device contains data and should be erased before
  writing unless you intend to overwrite it.

### 9.4 Erase

Electrically erases the selected device.

DESTRUCTIVE ACTION: All chip contents will be permanently lost.

Workflow:

1. Open `IC Ops` and click `Erase`.
2. A confirmation dialog appears with the chip name and a warning.
3. Two optional checkboxes are available:
   - `Blank check after erase` (enabled by default): runs a blank check
     immediately after erase to confirm the device is fully cleared.
   - `Read after erase` (disabled by default): reads the device contents
     into the hex panel after erasing.
4. Press `Enter` to confirm or `Escape` to cancel.
5. A progress bar tracks the erase operation.

UV EPROM handling:

- Some older EPROMs, such as the 27C-series, cannot be erased electrically.
- For these devices the `Erase` button in the IC operations menu is disabled
  (greyed out), and a UV-erase notice is shown below it.
- These parts require a UV eraser lamp (approximately 253 nm for roughly
  30 minutes). MiniGecko cannot perform or trigger this process.

### 9.5 Compare vs File

Reads the current device contents and compares them byte-by-byte against a
reference file you choose.

Workflow:

1. Open `IC Ops` and click `Compare vs file…`.
2. The file picker opens. Select the reference binary.
3. MiniGecko reads the device to a temporary file.
4. The two files are compared byte-by-byte.
5. The action log reports the result.

Result interpretation:

- Match: the action log reports identical byte counts.
- Mismatch: the log reports how many bytes differ and the percentage mismatch.
- Size mismatch: if the device read and reference file are different sizes,
  this is logged as a separate size warning before the comparison.

### 9.6 RAM or Logic Test

Runs `minipro`'s built-in test vector suite against SRAM and logic ICs.

Supported device types:

- SRAM devices.
- Logic ICs with test vectors defined in `minipro`'s `logicic.xml` database.

Workflow:

1. Select an SRAM or logic IC and open `IC Ops`.
2. Click `RAM / Logic Test`.
3. `minipro` drives the test vectors and reports results.
4. The action log shows the outcome.

Result interpretation:

- Pass: the log reports all cells or vectors passed.
- Fail: the log reports the error count, summary, and a per-pin detail table
  when available.

### 9.7 Pin Check

Verifies that all device pins make proper electrical contact in the ZIF socket.

Workflow:

1. Open `IC Ops` and click `Pin Check`.
2. `minipro` checks each pin for contact.
3. The action log reports pass or fail.

Result interpretation:

- Pass (`all pins contact`): the device is seated correctly.
- Fail: the action log shows which pins failed contact. This usually indicates
  a seating issue.

Troubleshooting:

- Remove and re-insert the device, ensuring correct orientation and alignment.
- Ensure pins are not bent.
- Clean the ZIF socket contacts if contact failures persist.
- Run pin check again before any write or erase operation to confirm seating.

## 10. Safety and Best Practices

### 10.1 Before You Program

Run through this checklist before any write or erase operation.

Device identity:

- Confirm the full part number on the physical device matches the chip you
  selected in MiniGecko.
- Check the package type and pin count in the IC information panel match
  the physical device.
- If the chip ID flag is enabled for the device, review any chip ID mismatch
  warnings in the action log before continuing.

Orientation and seating:

- Insert the device into the ZIF socket in the correct orientation. Most DIP
  packages have pin 1 marked with a notch or dot.
- Confirm the lever is fully closed.
- Run a pin check before programming to detect poor contact early.

Data source:

- Confirm the file loaded in the hex panel is the correct binary.
- If you have any doubt, compare it against a known-good reference using
  `Compare vs file…` before writing.

### 10.2 Destructive Operations

Write and erase operations permanently alter device contents and cannot be
undone from within MiniGecko.

Before erasing:

- If the device contains data you may need again, read it first and save the
  result to a file using `Write to file`.
- Keep at least one backup copy of original device contents before erasing
  or overwriting, especially for one-time-programmable or hard-to-source parts.

Before writing:

- Erase the device first if it is not already blank, unless the device
  supports overwrite without prior erase (some EEPROMs do).
- Use `Blank Check` to confirm the device is ready before writing.

After writing:

- Leave `Verify after write` enabled unless you have a specific reason to
  skip it. A failed verify immediately after a successful write usually
  indicates a seating issue or a marginal device.

WARNING: There is no undo. Once erased or overwritten, the previous device
contents are gone.

### 10.3 Verification Strategy

Use MiniGecko's built-in verification tools as a routine part of every
programming session, not just when something looks wrong.

Recommended sequence for writing a device:

1. Read the blank or original device and save it as a backup file.
2. Run Blank Check to confirm the device is ready for writing.
3. Write the target binary with `Verify after write` enabled.
4. If verify reports a mismatch, re-seat the device, run Pin Check, and
   repeat the write.

Additional spot-checks:

- Use `Compare vs file…` after a session to confirm device contents match
  your source binary independently of the write operation's own verify step.
- After an erase, always run Blank Check before writing. Even if the erase
  reported success, a failed blank check indicates a problem worth
  investigating before you commit new data.

For critical or hard-to-replace devices:

- Read back and save the programmed contents to a separate file.
- Diff that file externally against your source binary if you want a third
  point of confirmation beyond MiniGecko's built-in compare.

## 11. Configuration and Persistence

### 11.1 State File

MiniGecko stores persistent UI state in a JSON file at:

```
~/.config/minigecko/state.json
```

The file is created automatically on first run. MiniGecko reads it at startup
and writes it when you resize panels, open files, or quit the application.
You do not normally need to edit this file by hand, but you can do so when
MiniGecko is not running.

Fields stored in `state.json`:

| Field | Default | Description |
| --- | --- | --- |
| `hex_panel_width` | `66` | Width of the hex panel in terminal columns. |
| `info_panel_height` | `18` | Height of the IC information panel in rows. |
| `last_directory` | Home directory | Last directory opened in the file picker. |
| `minipro_path` | `""` (empty) | Absolute path to the `minipro` binary. Empty means find it on `PATH`. |

If the state file is missing, corrupt, or unreadable, MiniGecko falls back
to built-in defaults and logs a warning. Panel sizes revert to defaults
and the file picker starts in your home directory.

To reset the state file:

```bash
rm ~/.config/minigecko/state.json
```

### 11.2 Environment Variables

`MINIGECKO_EMULATE`

- Set to `1` to activate emulator mode.
- Replaces the real `minipro` transport with a simulated backend.
- No hardware or `minipro` binary is required.
- Useful for UI testing and workflow rehearsal.
- Must be set before launch; changing it while MiniGecko is running has
  no effect.

```bash
MINIGECKO_EMULATE=1 minigecko
```

`MINIPRO_HOME`

- Set to the directory containing `minipro`'s data files, including
  `logicic.xml` (the logic IC test vector database).
- When set, MiniGecko checks `$MINIPRO_HOME/logicic.xml` first before
  falling back to the standard system locations
  (`/usr/local/share/minipro/` and `/usr/share/minipro/`).
- Use this variable if your `minipro` was installed to a non-standard
  location or if you are testing with a custom device database.

```bash
MINIPRO_HOME=/opt/minipro/share minigecko
```

### 11.3 Custom minipro Path

If `minipro` is installed to a non-standard location and is not on your
`PATH`, you can tell MiniGecko where to find it by setting the
`minipro_path` field in the state file.

To configure a custom path, edit `~/.config/minigecko/state.json` while
MiniGecko is not running:

```json
{
  "minipro_path": "/opt/minipro/bin/minipro"
}
```

Behavior:

- When `minipro_path` is set to a non-empty string, MiniGecko uses that
  absolute path directly instead of searching `PATH`.
- If the path does not point to an existing file, MiniGecko reports
  `minipro not found` — it does not fall back to `PATH` lookup.
- Set `minipro_path` back to an empty string (`""`) to revert to `PATH`
  lookup.

## 12. Troubleshooting

### 12.1 Programmer Not Detected

Symptom: The application subtitle shows `Programmer: not detected` or
operations immediately fail with a message about no programmer found.

Check the USB connection:

- Confirm the programmer is plugged in and the USB cable is properly seated.
- Try a different USB port or cable.
- Unplug and replug the programmer.

Verify `minipro` can see the device:

```bash
minipro --version
```

When a programmer is connected, this should print a `Found <model> <fw>`
line. If it does not, the issue is below MiniGecko at the `minipro` or
USB layer.

Check USB permissions:

- By default, USB devices may require root access on Linux.
- If `sudo minipro --version` works but `minipro --version` does not,
  your user account lacks permission to access the programmer.
- Add a `udev` rule for your programmer's USB vendor ID:

```bash
# Example for TL866II+ (vendor ID 04d8)
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="04d8", MODE="0666", GROUP="plugdev"' \
  | sudo tee /etc/udev/rules.d/99-minipro.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

- Then log out and back in, or run `newgrp plugdev`.

Verify `minipro` is on your `PATH`:

```bash
which minipro
```

If this returns nothing, `minipro` is either not installed or not accessible.
See section 3.1 for install steps, or configure `minipro_path` in the state
file as described in section 11.3.

Use emulator mode to isolate TUI issues:

```bash
MINIGECKO_EMULATE=1 minigecko
```

If MiniGecko behaves correctly in emulator mode, the problem is with
hardware or `minipro` rather than the application itself.

### 12.2 Operation Fails Midway

Symptom: Read, write, erase, or verify starts but stops before completion,
or reports an unexpected error from `minipro`.

Check device seating:

- Open the ZIF lever, remove the device, and re-insert it carefully.
- Confirm correct orientation (pin 1 toward the lever end, usually).
- Close the lever fully.
- Run Pin Check before retrying.

Check for a chip ID mismatch warning:

- If the action log shows a chip ID warning, confirm that the device you
  selected matches the physical part.
- A mismatch does not always prevent the operation, but it is a strong signal
  that the wrong part is selected.

For write failures after erase:

- Run Blank Check to confirm the device was fully erased.
- If Blank Check fails, the erase may have been incomplete. Try erasing again.

For operations that time out:

- MiniGecko applies a 120-second timeout to each `minipro` call.
- If an operation consistently times out, the device may be damaged, the
  programmer may be hanging, or the USB connection may be unstable.
- Unplug and replug the programmer and retry.

### 12.3 Device Not in Database

Symptom: Searching for your chip in the chip selector returns no results.

The device list comes directly from `minipro -l`. If your chip is missing:

Check the installed `minipro` version:

```bash
minipro --version
```

Older `minipro` versions have smaller device databases. Update `minipro` to
get support for more devices:

```bash
# Debian / Ubuntu
sudo apt update && sudo apt install minipro

# From source
git clone https://gitlab.com/DavidGriffith/minipro
cd minipro && make && sudo make install
```

Search using a partial name:

- Try shorter or alternative spellings. For example, `28C256` instead of
  `AT28C256`.
- Try filtering by category first to narrow the list.

If the chip is genuinely unsupported by your `minipro` build, there is no
workaround from within MiniGecko. Check the `minipro` issue tracker or
device database to see if support is planned or available in a newer build.

### 12.4 UI Issues

Symptom: The interface renders incorrectly, appears blank, or keys do not
respond as expected.

Terminal compatibility:

- MiniGecko requires a modern terminal emulator with standard keyboard and
  ANSI color support.
- Recommended terminals: GNOME Terminal, Alacritty, kitty, WezTerm, tmux
  (with a compatible inner terminal), or any terminal that supports Textual
  applications.
- If the UI appears garbled, try a different terminal emulator.
- Avoid running inside very old or stripped-down terminal emulators that
  lack color or proper input handling.

Resize behavior:

- MiniGecko reflows its layout when the terminal window is resized.
- If panels appear misaligned after a resize, try pressing `Ctrl+L` or
  resizing the terminal window slightly to force a redraw.
- Panel split positions are saved to the state file. If the saved sizes are
  no longer valid after a terminal resize, delete `~/.config/minigecko/state.json`
  to reset them.

Keyboard shortcuts not working:

- Some terminal emulators or multiplexers intercept key combinations before
  they reach the application.
- If `Ctrl+Q` does not quit, check whether your terminal or tmux is
  capturing it. Try using the command palette (`Ctrl+P`) to access quit.

Application fails to start:

- Confirm Python 3.11 or newer:

  ```bash
  python3 --version
  ```

- Confirm the `minigecko` entry point is installed:

  ```bash
  which minigecko
  ```

- If `minigecko` is not found after `pip install -e .`, confirm your
  Python environment's `bin` directory is on your `PATH`.

## 13. Glossary

**Blank check**
A test that reads every byte of a device and confirms each one is `0xFF`,
the erased state for most Flash and EEPROM devices. A device that passes
blank check is ready to program.

**DIP (Dual Inline Package)**
A common IC package format with two parallel rows of through-hole pins.
Most EPROMs and EEPROMs targeted by `minipro` use DIP packages.

**EEPROM (Electrically Erasable Programmable Read-Only Memory)**
A non-volatile memory type that can be erased and rewritten electrically,
typically byte by byte or page by page without a separate erase step.

**EPROM (Erasable Programmable Read-Only Memory)**
An older non-volatile memory type programmed electrically but erased by
exposure to ultraviolet light (UV EPROM). Erase requires a UV lamp; the
programmer hardware cannot erase these devices.

**Flash**
A type of EEPROM that is erased and written in blocks or sectors rather
than byte by byte. Common in embedded systems and modern storage devices.

**ISP (In-System Programming)**
The ability to program a device while it remains installed in a circuit,
using a programming header rather than removing and socketing the chip.
The IC information panel indicates ISP support for applicable devices.

**OTP (One-Time Programmable)**
A device that can be programmed once and cannot be erased. Treat OTP
writes as permanent and verify carefully before committing data.

**PLD (Programmable Logic Device)**
A category of configurable logic ICs, including PALs, GALs, and CPLDs.
`minipro` supports programming and reading a range of PLD families.

**SRAM (Static Random-Access Memory)**
A volatile memory device that retains data only while powered. `minipro`
can run functional test vectors against SRAM to verify correct operation.

**VCC**
The positive supply voltage pin of a device. The IC information panel may
report the default VCC voltage for the selected chip.

**VPP (Programming Voltage)**
An elevated supply voltage applied to certain devices during programming
or erase operations. The programmer hardware manages VPP automatically;
MiniGecko and `minipro` handle the sequencing transparently.

**Verify**
A post-write step that reads the device back and compares it byte-by-byte
against the source file. MiniGecko enables `Verify after write` by
default. A failed verify indicates that the write did not complete
correctly.

**ZIF (Zero Insertion Force) socket**
The lever-operated socket on the programmer that holds the target IC
during operations. Opening the lever releases the chip with minimal
force. A fully closed lever is required for reliable contact.

## 14. Quick Reference

### Launch

| Command | Effect |
| --- | --- |
| `minigecko` | Start the TUI |
| `minigecko tui` | Start the TUI (explicit) |
| `MINIGECKO_EMULATE=1 minigecko` | Start in emulator mode (no hardware required) |
| `minigecko version` | Print installed version |
| `minigecko detect` | Report programmer detection status |

### Global Keys

| Key | Action |
| --- | --- |
| `f` | Open file picker |
| `s` | Open chip selector |
| `d` | Open IC operations (requires chip selected) |
| `Ctrl+D` | Toggle dark / light theme |
| `Ctrl+P` | Open command palette |
| `Ctrl+Q` | Quit |

### Chip Selector Dialog

| Key | Action |
| --- | --- |
| Type to search | Filter by name (case-insensitive) |
| `Left` / `Right` | Cycle through chip type categories (when search box is empty) |
| `Up` / `Down` | Move between results (works from the search input) |
| `Enter` | Select highlighted device |
| `Escape` | Cancel |

### IC Operations Dialog

| Key | Action |
| --- | --- |
| `Up` / `Down` | Move between operations |
| `Enter` | Activate highlighted operation |
| `Escape` | Close dialog |

### Write Confirmation Dialog

| Key | Action |
| --- | --- |
| `Space` | Toggle `Verify after write` |
| `Enter` | Confirm write |
| `Escape` | Cancel |

### Erase Confirmation Dialog

| Key | Action |
| --- | --- |
| `Space` | Toggle selected checkbox |
| `Enter` | Confirm erase |
| `Escape` | Cancel |

### Hex View Modal

| Key | Action |
| --- | --- |
| `Up` / `Down` | Scroll one line |
| `PgUp` / `PgDn` | Scroll one page |
| `Home` | Jump to top |
| `End` | Jump to bottom |
| `Escape` | Close |

### Device Operation Summary

| Operation | Destructive | Requires data loaded | Notes |
| --- | --- | --- | --- |
| Read from device | No | No | Loads result into hex panel |
| Write to device | Yes | Yes | Confirm dialog; verify enabled by default |
| Blank check | No | No | Pass = all `0xFF` |
| Erase | Yes | No | Unavailable for UV EPROMs |
| Compare vs file | No | No | Opens file picker for reference binary |
| RAM / Logic test | No | No | SRAM and logic ICs only |
| Pin check | No | No | Confirms ZIF socket contact |
| Write to file | No | Yes | Saves in-memory buffer to disk |

### Common File Paths

| Path | Purpose |
| --- | --- |
| `~/.config/minigecko/state.json` | Persistent UI state |

### Environment Variables

| Variable | Value | Effect |
| --- | --- | --- |
| `MINIGECKO_EMULATE` | `1` | Enable emulator mode |
| `MINIPRO_HOME` | `/path/to/dir` | Override `minipro` data file location |

## 15. Revision History

| Version | Date | Notes |
| --- | --- | --- |
| 0.1 | 2026-03-19 | Initial skeleton |
| 0.2 | 2026-03-19 | All sections complete |

## Appendix A: Fill Progress Checklist

- [x] About This Manual
- [x] What MiniGecko Is
- [x] Installation and Setup
- [x] Starting MiniGecko
- [x] Interface Tour
- [x] Keyboard Shortcuts
- [x] Chip Selection
- [x] File Operations
- [x] Device Operations
- [x] Safety and Best Practices
- [x] Configuration and Persistence
- [x] Troubleshooting
- [x] Glossary
- [x] Quick Reference