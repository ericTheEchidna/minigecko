[Back to Table of Contents](toc.md)

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
