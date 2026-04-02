[Back to Table of Contents](toc.md)

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
