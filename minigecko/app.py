"""minigecko.app
~~~~~~~~~
Compatibility module for launching the Textual application.
"""

from __future__ import annotations

from minigecko.ui.app_shell import MinigeckoApp


def main() -> None:
    MinigeckoApp().run()


if __name__ == "__main__":
    main()
