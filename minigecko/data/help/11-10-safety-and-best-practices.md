[Back to Table of Contents](toc.md)

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
