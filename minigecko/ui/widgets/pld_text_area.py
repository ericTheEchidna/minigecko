"""A text area that colours GALasm (Galette) and CUPL (WinCUPL) sources.

Neither language has a tree-sitter grammar, so the colours come from
regular expressions, line by line. Highlight names are the ones Textual's
editor themes already colour (comment, keyword, operator, …).
"""

from __future__ import annotations

import re

from textual.widgets import TextArea

from minigecko.core.pld import CUPL, GALASM, pld_language

# (start, end, highlight name) in UTF-8 byte offsets, as TextArea expects.
Span = tuple[int, int, str]

_OPERATORS = re.compile(r"[*+/=#&!$:]")
_GALASM_SUFFIX = re.compile(r"\.(R|E|T|CLK|ARST|APRST)\b", re.IGNORECASE)
_GALASM_SPECIAL = re.compile(r"\b(AR|SP)\b")
_POWER = re.compile(r"\b(NC|GND|VCC)\b")
_CUPL_KEYWORD = re.compile(
    r"^\s*(Name|Partno|Date|Revision|Rev|Designer|Company|Assembly|Assy|Location|Device|"
    r"Format|Pin|Pinnode|Field|Table|Property|Min|Sequence|Sequenced|Sequencer|"
    r"Present|Next|Out|Default|Condition|Function|Append)\b",
    re.IGNORECASE,
)
_CUPL_DEVICE = re.compile(r"^\s*device\s+(\S+?)\s*;", re.IGNORECASE)
_CUPL_SUFFIX = re.compile(
    r"\.(OE|D|T|J|K|S|R|L|LE|CK|CKMUX|AR|SP|AP|IO|DQ|LQ|SR|CE|INT|OEMUX|IMUX|BYP|DFB|LFB|TFB)\b",
    re.IGNORECASE,
)
_CUPL_NUMBER = re.compile(r"'[bBoOdDhH]'[0-9A-Fa-fXx]+|\b\d+\b")


def _span(line: str, start: int, end: int, name: str) -> Span:
    """Character offsets on *line* as the byte offsets TextArea draws with."""
    return (len(line[:start].encode()), len(line[:end].encode()), name)


def _matches(line: str, pattern: re.Pattern, name: str, group: int = 0) -> list[Span]:
    return [_span(line, m.start(group), m.end(group), name) for m in pattern.finditer(line)]


def galasm_highlights(lines: list[str]) -> dict[int, list[Span]]:
    """Colours for a GALasm source, by line index."""
    out: dict[int, list[Span]] = {}
    meaningful = 0  # chip, signature, two pin lists, then equations
    in_description = False
    for row, line in enumerate(lines):
        spans: list[Span] = []
        if in_description:
            out[row] = [_span(line, 0, len(line), "comment")]
            continue
        code, sep, _comment = line.partition(";")
        if sep:
            spans.append(_span(line, len(code), len(line), "comment"))
        stripped = code.strip()
        if stripped:
            if stripped == "DESCRIPTION":
                in_description = True
                spans.append(_span(line, code.index("DESCRIPTION"), len(code), "keyword"))
            elif meaningful == 0:  # the chip
                spans.append(_span(line, code.index(stripped), len(code.rstrip()), "type.builtin"))
            elif meaningful == 1:  # the signature: free text
                spans.append(_span(line, code.index(stripped), len(code.rstrip()), "string"))
            else:
                spans += _matches(code, _POWER, "constant.builtin")
                spans += _matches(code, _OPERATORS, "keyword.operator")
                if meaningful > 3:  # equations
                    spans += _matches(code, _GALASM_SUFFIX, "method")
                    spans += _matches(code, _GALASM_SPECIAL, "keyword")
            meaningful += 1
        if spans:
            out[row] = spans
    return out


def cupl_highlights(lines: list[str]) -> dict[int, list[Span]]:
    """Colours for a CUPL source, by line index. /* */ comments may span lines."""
    out: dict[int, list[Span]] = {}
    in_comment = False
    for row, line in enumerate(lines):
        spans: list[Span] = []
        code_parts: list[tuple[int, str]] = []  # (offset, text) outside comments
        pos = 0
        while pos <= len(line):
            if in_comment:
                end = line.find("*/", pos)
                stop = len(line) if end < 0 else end + 2
                spans.append(_span(line, pos, stop, "comment"))
                if end < 0:
                    break
                in_comment, pos = False, stop
            else:
                start = line.find("/*", pos)
                if start < 0:
                    code_parts.append((pos, line[pos:]))
                    break
                code_parts.append((pos, line[pos:start]))
                in_comment, pos = True, start
        for offset, part in code_parts:
            for pattern, name in (
                (_CUPL_NUMBER, "number"),
                (_OPERATORS, "keyword.operator"),
                (_CUPL_SUFFIX, "method"),
            ):
                for m in pattern.finditer(part):
                    spans.append(_span(line, offset + m.start(), offset + m.end(), name))
            if offset == 0:
                keyword = _CUPL_KEYWORD.match(part)
                if keyword:
                    spans.append(_span(line, keyword.start(1), keyword.end(1), "keyword"))
                device = _CUPL_DEVICE.match(part)
                if device:
                    spans.append(_span(line, device.start(1), device.end(1), "type.builtin"))
        if spans:
            out[row] = spans
    return out


class PldTextArea(TextArea):
    """TextArea that colours GALasm and CUPL when ``pld`` is True.

    Overrides TextArea._build_highlight_map, a private Textual method (8.1):
    Textual calls it after every load and edit to fill ``_highlights``.
    tests/test_app_tabs.py fails if a Textual update stops calling it.
    """

    pld = False  # set True for a .pld source; other text stays plain

    def _build_highlight_map(self) -> None:
        if not self.pld:
            super()._build_highlight_map()
            return
        self._line_cache.clear()
        self._highlights.clear()
        text = self.text
        language = pld_language(text)
        if language is None:
            return
        lines = text.split("\n")
        build = galasm_highlights if language == GALASM else cupl_highlights
        for row, spans in build(lines).items():
            self._highlights[row].extend(spans)
