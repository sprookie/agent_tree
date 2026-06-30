from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import TextArea


class TaskInput(Widget):
    """Multi-line task input widget with @tree syntax support."""

    DEFAULT_CSS = """
    TaskInput {
        height: auto;
        min-height: 5;
        max-height: 14;
    }
    TaskInput TextArea {
        height: auto;
        min-height: 5;
        max-height: 12;
    }
    """

    BINDINGS = [("ctrl+enter", "submit", "Submit")]

    def compose(self) -> ComposeResult:
        placeholder = (
            "Enter task here. Use @tree syntax for hierarchical tasks:\n"
            "@tree\n"
            "Analyse the Linux kernel scheduler\n"
            "  - Analyse CFS core logic\n"
            "      - Key data structures\n"
            "  - Analyse real-time scheduling"
        )
        yield TextArea(id="task-textarea", language=None)

    def get_text(self) -> str:
        try:
            ta = self.query_one("#task-textarea", TextArea)
            return ta.text
        except Exception:
            return ""

    def clear(self) -> None:
        try:
            ta = self.query_one("#task-textarea", TextArea)
            ta.clear()
        except Exception:
            pass

    def action_submit(self) -> None:
        self.app.action_submit_task()
