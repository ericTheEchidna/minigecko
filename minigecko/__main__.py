"""
minigecko.__main__
~~~~~~~~~~~~~~
Entry point for both `python -m minigecko` and the `minigecko` console script.

Top-level commands:
  minigecko tui        Launch the Textual TUI (default with no args)
  minigecko detect     Quick programmer detection
  minigecko version    Print version and exit
"""

from __future__ import annotations

import click

from minigecko import __version__


@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def cli(ctx: click.Context) -> None:
    """minigecko — open source TUI programmer suite powered by minipro.

    Run without arguments to launch the interactive TUI.
    """
    if ctx.invoked_subcommand is None:
        # No sub-command → launch TUI
        _launch_tui()


# ---------------------------------------------------------------------------
# Built-in top-level commands
# ---------------------------------------------------------------------------

@cli.command("tui")
def tui_cmd() -> None:
    """Launch the interactive TUI."""
    _launch_tui()


@cli.command("version")
def version_cmd() -> None:
    """Print version information and exit."""
    click.echo(f"minigecko {__version__}")


@cli.command("detect")
def detect_cmd() -> None:
    """Detect a connected programmer."""
    from minigecko.core import detect_programmer, is_available
    if not is_available():
        click.echo(
            "minipro not found on PATH.\n"
            "Install it from: https://gitlab.com/DavidGriffith/minipro",
            err=True,
        )
        raise SystemExit(1)
    info = detect_programmer()
    if info.connected:
        click.echo(f"[OK] {info.hardware}  firmware {info.firmware}")
    else:
        click.echo("[FAIL] No programmer detected.", err=True)
        if info.raw:
            click.echo(info.raw, err=True)
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# TUI launcher
# ---------------------------------------------------------------------------

def _launch_tui() -> None:
    from minigecko.app import MinigeckoApp
    app = MinigeckoApp()
    app.run()


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

def main() -> None:
    cli(prog_name="minigecko")


if __name__ == "__main__":
    main()
