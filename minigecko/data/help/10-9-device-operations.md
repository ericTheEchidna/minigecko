[Back to Table of Contents](toc.md)

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
