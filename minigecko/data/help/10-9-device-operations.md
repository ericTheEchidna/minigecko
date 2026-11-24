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
4. Optionally toggle the `Read back and verify` checkbox (enabled by default).
5. Press `Enter` to confirm or `Escape` to cancel.
6. A progress bar shows streaming percentage while the write runs.
7. If verify is enabled, `minipro` reads the device back in the same pass
   and compares it with the file. On a mismatch the log names the first
   address that differs.

### 9.3 Blank Check

Verifies that every byte in the selected device reads as `0xFF`, indicating
the chip is in a fully erased state.

Workflow:

1. Open `IC Ops` and click `Blank Check`.
2. MiniGecko checks pin contact first. An empty or badly seated socket reads
   as all `0xFF`, so without this step it would look blank.
3. If every pin makes contact, `minipro` checks the device contents.
4. The action log reports blank, not blank (with the first used byte), or
   failed. A failed check says nothing about the chip's contents.

Result interpretation:

- Blank (`every byte reads 0xFF`): the device is blank and ready to program.
- Not blank: the device contains data and should be erased before
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

### 9.8 Programming GALs and Other PLDs

GALs and Atmel ATF PLDs (ATF16V8B, GAL22V10 and similar) are programmed from a
JEDEC fuse file (`.jed`), the output of WinCUPL, GALasm or openCUPL. MiniGecko
uses the JEDEC format automatically when a PLD is selected.

Workflow:

1. Select the chip by its exact marking, suffix included. An ATF16V8B and an
   ATF16V8C need different profiles: the C has one more fuse.
2. Press `f` and open the `.jed` file.
3. Open `IC Ops` and click `Write to device`. MiniGecko first checks that the
   file fits the chip (see below), then shows the confirmation.
4. The chip is erased, written and read back to verify, in one pass.

Before anything is written, MiniGecko refuses a file when:

- its fuse count differs from the chip's, for example a 22V10 file (5892
  fuses) for a 16V8 chip (2194 fuses). The message quotes the file's `Device`
  line, such as `g22v10`;
- its fuse checksum does not match its fuses, which means the file is damaged;
- it has no fuse count at all, so it is not a JEDEC file.

`minipro` itself only warns about the first two and writes anyway, so this
check matters.

When a `.jed` is open or read from a chip, the Data tab shows its fuse map
beside its logic equations, decompiled by MAME's `jedutil` (install it with
`sudo pacman -S mame-tools`). If a `.pld` with the same name sits beside the
`.jed`, the equations use its signal names, with active-low pins read the way
the source declares them: `WR` means ~WR is asserted. An equation list with no
logic means the chip is blank or was secured.

Reading a PLD saves a `.jed` file, which `Ctrl+S` can store and which can be
written back later. A chip whose security fuse is set reads back blank, so
for a secured chip the verify step during the write is the only check.
