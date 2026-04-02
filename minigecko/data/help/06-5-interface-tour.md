[Back to Table of Contents](toc.md)

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
