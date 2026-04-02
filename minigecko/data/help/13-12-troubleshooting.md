[Back to Table of Contents](toc.md)

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
