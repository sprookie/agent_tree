"""TaskInput widget — multiline input with @tree syntax support."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Vertical
from textual.widgets import Static, TextArea

from agent_tree.tree_parser import TreeParser

if TYPE_CHECKING:
    from textual.app import ComposeResult


class TaskInput(Vertical):
    """Input area with @tree syntax and live preview."""

    DEFAULT_CSS = """
    TaskInput {
        height: auto;
        dock: bottom;
        padding: 1 2;
        border-top: solid $primary;
        background: $surface;
    }
    TaskInput TextArea {
        height: 8;
        margin: 1 0;
    }
    TaskInput .input-hint {
        color: $text-muted;
        height: 1;
    }
    """

    def compose(self) -> "ComposeResult":
        yield Static("Enter task with @tree syntax (Ctrl+R to run):", classes="input-hint")
        yield TextArea(text="", id="task-textarea")
        yield Static("", id="tree-preview", classes="input-hint")

    @property
    def input_text(self) -> str:
        textarea = self.query_one("#task-textarea", TextArea)
        return textarea.text

    def on_text_area_changed(self) -> None:
        text = self.input_text
        if "@tree" in text:
            parser = TreeParser()
            tree = parser.parse(text)
            preview = self.query_one("#tree-preview", Static)
            if tree:
                count = len(tree.children)
                preview.update(f"Parsed: {count} top-level tasks, max depth OK")
            else:
                preview.update("Parsing tree...")
