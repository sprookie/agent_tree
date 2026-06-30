from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import TextArea

_PLACEHOLDER = """\
@tree
Analyse the Linux kernel scheduler
  - Analyse CFS core logic
      - Key data structures
      - Scheduling entry functions
  - Analyse real-time scheduling
      - FIFO/RR implementation\
"""


class TaskInput(Widget):
    """Multi-line task input with @tree syntax support.

    Ctrl+Enter submits. Tab inserts 2-space indent.
    """

    DEFAULT_CSS = """
    TaskInput {
        height: auto;
        min-height: 6;
        max-height: 15;
    }
    TaskInput TextArea {
        height: auto;
        min-height: 6;
        max-height: 13;
        border: none;
    }
    """

    BINDINGS = [
        Binding("ctrl+enter", "submit", "Submit", show=True, priority=True),
    ]

    def compose(self) -> ComposeResult:
        ta = TextArea(id="task-textarea")
        ta.load_text(_PLACEHOLDER)
        yield ta

    def on_mount(self) -> None:
        # Select all placeholder text so first keystroke replaces it
        ta = self.query_one("#task-textarea", TextArea)
        ta.select_all()

    def get_text(self) -> str:
        try:
            return self.query_one("#task-textarea", TextArea).text
        except Exception:
            return ""

    def clear(self) -> None:
        try:
            self.query_one("#task-textarea", TextArea).clear()
        except Exception:
            pass

    def action_submit(self) -> None:
        self.app.action_submit_task()

    def on_key(self, event) -> None:
        """Intercept ctrl+enter even when TextArea consumes keys."""
        if event.key == "ctrl+enter":
            event.stop()
            event.prevent_default()
            self.action_submit()
