[Back to Table of Contents](toc.md)

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
