"""Help screen — renders the user manual via MarkdownViewer."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from time import monotonic

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import LoadingIndicator, Markdown, MarkdownViewer, Static

_HELP_DIR = Path(__file__).parent.parent.parent / "data" / "help"
_TOC_PAGE = "toc.md"
_DEFAULT_PAGE = "01-overview.md"
_CACHED_PAGES: set[str] = set()


def _resolve_page(page: str) -> Path | None:
    """Resolve a relative help page path safely under the help directory."""
    if not page or page.startswith(("http://", "https://", "mailto:")):
        return None
    if page.startswith("#"):
        return None

    rel = Path(page)
    if rel.is_absolute() or rel.suffix.lower() != ".md":
        return None

    help_root = _HELP_DIR.resolve()
    target = (_HELP_DIR / rel).resolve()
    if help_root != target and help_root not in target.parents:
        return None
    return target


@lru_cache(maxsize=32)
def load_help_text(page: str) -> str:
    """Read and cache a help markdown page by relative path."""
    target = _resolve_page(page)
    if target is None:
        return "_Invalid help link._"

    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        text = "_Help page not found._"
    _CACHED_PAGES.add(page)
    return text


def load_manual_text() -> str:
    """Compatibility loader used by app startup preload logic."""
    return load_help_text(_TOC_PAGE)


def is_manual_cached() -> bool:
    """Return True when the TOC help page has already been cached."""
    return _TOC_PAGE in _CACHED_PAGES


class HelpToc(Markdown):
    """Left-pane help TOC that routes internal links back into the modal."""

    def __init__(self, markdown: str, navigate: Callable[[str], None]) -> None:
        super().__init__(markdown, id="help-toc", open_links=False)
        self._navigate = navigate

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        event.stop()
        href = event.href
        if href.startswith(("http://", "https://", "mailto:")):
            self.app.open_url(href)
            return
        self._navigate(href)


class HelpContentViewer(MarkdownViewer):
    """Right-pane markdown viewer with in-app navigation for help pages."""

    def __init__(self, markdown: str, navigate: Callable[[str], None]) -> None:
        super().__init__(
            markdown,
            id="help-content-viewer",
            show_table_of_contents=False,
            open_links=False,
        )
        self._navigate = navigate

    async def _on_markdown_link_clicked(self, message: Markdown.LinkClicked) -> None:
        message.stop()
        href = message.href
        if href.startswith("#"):
            await self.go(href)
            return
        if href.startswith(("http://", "https://", "mailto:")):
            self.app.open_url(href)
            return
        self._navigate(href)


class HelpScreen(ModalScreen[None]):
    """Full-screen modal displaying the MiniGecko user manual."""

    DEFAULT_CSS = """
    HelpScreen { align: center middle; }
    #help-frame {
        width: 92%;
        height: 92%;
        border: thick $primary;
        background: $surface;
    }
    #help-toc-pane {
        width: 32;
        min-width: 28;
        max-width: 40;
        height: 100%;
        border-right: solid $primary 30%;
        padding: 1;
    }
    #help-toc-title {
        width: 100%;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #help-toc {
        width: 100%;
        height: 1fr;
        background: $surface;
    }
    #help-content-pane {
        width: 1fr;
        height: 100%;
    }
    #help-content-title {
        width: 100%;
        padding: 1 2;
        border-bottom: solid $primary 20%;
        text-style: bold;
    }
    #help-content-host {
        width: 100%;
        height: 1fr;
    }
    #help-content-viewer {
        width: 100%;
        height: 100%;
        background: $surface;
    }
    #help-loading {
        width: 100%;
        height: 100%;
        align: center middle;
        padding: 0;
    }
    #help-loading-body {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1 2;
    }
    #help-loading-text {
        width: 100%;
        content-align: center middle;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Close", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._mounted_at = 0.0
        self._current_page = _DEFAULT_PAGE

    def compose(self) -> ComposeResult:
        with Horizontal(id="help-frame"):
            with Vertical(id="help-toc-pane"):
                yield Static("Help Topics", id="help-toc-title")
                yield HelpToc(load_help_text(_TOC_PAGE), self._navigate_to)
            with Vertical(id="help-content-pane"):
                yield Static("Help", id="help-content-title")
                with Vertical(id="help-content-host"):
                    yield HelpContentViewer("", self._navigate_to)
                    with Vertical(id="help-loading"):
                        with Vertical(id="help-loading-body"):
                            yield LoadingIndicator()
                            yield Static("Loading help...", id="help-loading-text")

    def on_mount(self) -> None:
        self._mounted_at = monotonic()
        self._schedule_navigation(self._current_page)

    @work(thread=True)
    def _load_help_page_async(self, page: str) -> None:
        text = load_help_text(page)
        self.app.call_from_thread(self._show_page, page, text)

    def _show_page(self, page: str, text: str) -> None:
        self.query_one("#help-content-title", Static).update(self._page_title(page, text))
        self._schedule_navigation(page)

    def _schedule_navigation(self, page: str) -> None:
        delay = max(0.0, 0.15 - (monotonic() - self._mounted_at))
        self.set_timer(delay, lambda: self.run_worker(self._go_to_page(page), exclusive=True))

    async def _go_to_page(self, page: str) -> None:
        viewer = self.query_one("#help-content-viewer", HelpContentViewer)
        await viewer.go(str((_HELP_DIR / page).resolve()))
        self._current_page = page
        self.call_after_refresh(self._remove_loading)

    def _remove_loading(self) -> None:
        try:
            self.query_one("#help-loading", Vertical).styles.display = "none"
        except Exception:
            pass

    def _show_loading(self, message: str) -> None:
        self.query_one("#help-loading", Vertical).styles.display = "block"
        self.query_one("#help-loading-text", Static).update(message)

    def _navigate_to(self, href: str) -> None:
        target = _resolve_page(href)
        if target is None:
            return

        rel = target.relative_to(_HELP_DIR.resolve()).as_posix()
        if rel == self._current_page:
            return
        self._mounted_at = monotonic()
        self._show_loading("Loading help...")
        self._load_help_page_async(rel)

    def _page_title(self, page: str, text: str) -> str:
        if page == _TOC_PAGE:
            return "Help"
        for line in text.splitlines():
            if line.startswith("#"):
                return line.lstrip("# ").strip()
        return page.removesuffix(".md").replace("-", " ").title()
