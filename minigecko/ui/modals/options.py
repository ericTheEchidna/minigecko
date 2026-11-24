"""Compiler options: which files Galette and WinCUPL write, and how."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from minigecko.core.pld import DEFAULT_COMPILER_OPTIONS, MINIMIZE_LEVELS

# (tool, key, label) for each check box, in screen order.
_CHECKS = [
    ("galette", "chp", "Pinout drawing (.chp)"),
    ("galette", "fus", "Fuse listing (.fus)"),
    ("galette", "pin", "Pin listing (.pin)"),
    ("galette", "secure", "Set the security fuse (-s)"),
    ("wincupl", "doc_equations", "Equations and product-term use in the .doc (-x)"),
    ("wincupl", "doc_fuse_plot", "Fuse plot in the .doc (-f)"),
    ("wincupl", "simulator", "Simulator files .abs and .sim (-a)"),
    ("wincupl", "macros", "Expanded macros, .mx (-e)"),
]


class OptionsScreen(ModalScreen):
    """Edit the compiler options. Dismisses with ``(options, wine_prefix)``,
    or None when cancelled."""

    DEFAULT_CSS = """
    OptionsScreen { align: center middle; }
    OptionsScreen > Vertical {
        width: 76; height: auto; max-height: 90%;
        border: thick $accent; background: $surface; padding: 1 2;
    }
    OptionsScreen .opt-title { text-style: bold; margin-bottom: 1; }
    OptionsScreen .opt-section { text-style: bold; color: $accent; margin-top: 1; }
    OptionsScreen .opt-note { color: $text-muted; }
    OptionsScreen .opt-risk { color: $error; padding-left: 4; }
    OptionsScreen VerticalScroll { height: auto; max-height: 30; }
    OptionsScreen Checkbox { border: none; padding: 0; }
    OptionsScreen Select { width: 100%; }  /* wide enough that no level's words wrap */
    OptionsScreen Input { width: 100%; }
    OptionsScreen #opt-buttons { height: auto; margin-top: 1; align-horizontal: right; }
    OptionsScreen #opt-buttons Button { margin-left: 2; }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, options: dict, wine_prefix: str) -> None:
        super().__init__()
        self._options = {
            tool: {**defaults, **options.get(tool, {})}
            for tool, defaults in DEFAULT_COMPILER_OPTIONS.items()
        }
        self._wine_prefix = wine_prefix

    def _check(self, tool: str, key: str, label: str) -> Checkbox:
        return Checkbox(label, value=bool(self._options[tool][key]), id=f"opt-{tool}-{key}")

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Compiler options", classes="opt-title")
            yield Static(
                "F9 compiles a .pld with Galette or WinCUPL, by its language. "
                "Both always write the .jed.",
                classes="opt-note",
            )
            with VerticalScroll():
                yield Label("Galette (GALasm sources)", classes="opt-section")
                for tool, key, label in _CHECKS[:4]:
                    yield self._check(tool, key, label)
                yield Static(
                    "Risk: a GAL with its security fuse set cannot be read or "
                    "verified until it is erased.",
                    classes="opt-risk",
                )
                yield Label("WinCUPL (CUPL sources)", classes="opt-section")
                for tool, key, label in _CHECKS[4:]:
                    yield self._check(tool, key, label)
                yield Static("With neither of the first two, there is no .doc.", classes="opt-note")
                yield Label("Minimisation", classes="opt-note")
                yield Select(
                    [(f"-m{n}  {words}", n) for n, words in MINIMIZE_LEVELS.items()],
                    value=int(self._options["wincupl"]["minimize"]),
                    allow_blank=False,
                    id="opt-wincupl-minimize",
                )
                yield Label("Wine prefix that holds WinCUPL (empty: ~/.wine-cupl)", classes="opt-note")
                yield Input(self._wine_prefix, placeholder="~/.wine-cupl", id="opt-wine-prefix")
            with Horizontal(id="opt-buttons"):
                yield Button("Cancel", id="opt-cancel")
                yield Button("Save", variant="primary", id="opt-save")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "opt-save":
            self.action_save()
        else:
            self.action_cancel()

    def action_save(self) -> None:
        options = {tool: dict(values) for tool, values in self._options.items()}
        for tool, key, _label in _CHECKS:
            options[tool][key] = self.query_one(f"#opt-{tool}-{key}", Checkbox).value
        options["wincupl"]["minimize"] = int(self.query_one("#opt-wincupl-minimize", Select).value)
        prefix = self.query_one("#opt-wine-prefix", Input).value.strip()
        self.dismiss((options, prefix))

    def action_cancel(self) -> None:
        self.dismiss(None)
