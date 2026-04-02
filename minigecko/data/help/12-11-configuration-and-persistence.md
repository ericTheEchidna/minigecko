[Back to Table of Contents](toc.md)

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
