[Back to Table of Contents](toc.md)

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
