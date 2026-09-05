"""HTML-escaping helpers. Everything the render puts on the page that came
from report data (order ids, basis text, drafted claim text, ...) goes
through ``esc`` so a stray ``<`` or ``&`` in a source row cannot break the
page or inject markup."""

from __future__ import annotations

from html import escape


def esc(value: object) -> str:
    if value is None:
        return ""
    return escape(str(value), quote=True)


def js_str(value: str) -> str:
    """Escape a string for embedding inside a single-quoted JS string literal
    within an HTML attribute (e.g. ``onclick="fn('...')"``)."""
    return value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
