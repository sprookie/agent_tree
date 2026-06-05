"""Message widgets for Agent Tree TUI."""

from __future__ import annotations

from time import time

from textual.containers import Vertical
from textual.content import Content
from textual.widgets import Static


class StatusMessage(Static):
    """A status line in the TUI."""
    DEFAULT_CSS = """
    StatusMessage {
        height: auto;
        padding: 0 1;
        color: $text-muted;
    }
    """
    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(Content.from_markup(f"[dim]{text}[/dim]"), **kwargs)
