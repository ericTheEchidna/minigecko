# MiniGecko working rules

## Missing tools: name them, no install commands
When MiniGecko (code, messages, help pages) meets a missing external tool, default to
naming the tool and what it is needed for; do not suggest `apt`, `pacman` or another
package-manager command. Give a project page or a path checked only where that helps.
Reason: Eric asked for this app-wide (2026-11-24); MINIGECKO-018 removes the old ones.

## Tests never touch the real UI state
App tests default to patching both `app_shell._load_state` (to `_DEFAULT_STATE`) and
`app_shell._save_state`; patch only `_save_state` when a test deliberately reads saved
values. Reason: a split-pane test failed because it loaded Eric's own saved split from
`~/.config/minigecko/state.json` (2026-11-24).

## Check an external tool's behaviour before describing it
Before describing a minipro, Galette, WinCUPL or jedutil option in code or help, default
to its source, its own help text (`strings cupl.exe`), or a run on a scratch copy; say
"from memory" when none is available. Reason: `-P` was once taken for skip-verify, and
WinCUPL's `-a`/`-e`/`-x`/`-f` outputs differed from what the flags' names suggest.
