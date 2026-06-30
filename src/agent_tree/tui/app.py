from __future__ import annotations

import asyncio
import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import Footer, Header, Label, Markdown, Static

from ..tree_executor import TreeExecutor
from ..tree_parser import TreeParser
from .adapter import TreeUIAdapter
from .widgets import TaskInput, TreeView


class TreeApp(App):
    """Agent Tree TUI — multi-level parallel sub-agent runner."""

    CSS_PATH = Path(__file__).parent / "styles.tcss"
    TITLE = "agent-tree"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+t", "focus_tree", "Tree", show=True),
        Binding("ctrl+i", "focus_input", "Input", show=True),
        Binding("ctrl+l", "clear_output", "Clear", show=True),
    ]

    def __init__(
        self,
        model: str | None = None,
        max_depth: int | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._model = model or os.environ.get("AGENT_TREE_MODEL", "openai:deepseek-v4-pro")
        self._max_depth = max_depth or int(os.environ.get("AGENT_TREE_MAX_DEPTH", "3"))
        self._executor_task: asyncio.Task | None = None
        self._adapter_task: asyncio.Task | None = None
        self._adapter: TreeUIAdapter | None = None

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="body"):
            with Horizontal(id="main-panels"):
                # Left: tree progress
                with Vertical(id="tree-panel"):
                    yield Label(" Tree Progress", id="tree-label")
                    yield TreeView()
                # Right: final report
                with Vertical(id="output-panel"):
                    yield Label(" Final Report", id="output-label")
                    with ScrollableContainer(id="output-scroll"):
                        yield Markdown("", id="output-content")
            # Bottom: task input
            with Vertical(id="input-panel"):
                yield Label(" Task  (Ctrl+Enter to submit · Ctrl+Q to quit)", id="input-label")
                yield TaskInput()
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = f"{self._model}  depth={self._max_depth}"
        tree_view = self.query_one(TreeView)
        self._adapter = TreeUIAdapter(tree_view, self._update_status)
        self.query_one(TaskInput).focus()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_focus_tree(self) -> None:
        self.query_one(TreeView).focus()

    def action_focus_input(self) -> None:
        self.query_one(TaskInput).focus()

    def action_clear_output(self) -> None:
        self.query_one("#output-content", Markdown).update("")
        self.query_one(TreeView).reset()
        self._update_status("cleared")

    def action_submit_task(self) -> None:
        task_input = self.query_one(TaskInput)
        text = task_input.get_text().strip()
        if not text:
            return
        task_input.clear()
        # Cancel any running task
        for t in [self._executor_task, self._adapter_task]:
            if t and not t.done():
                t.cancel()
        self._executor_task = asyncio.create_task(self._run_task(text))

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    async def _run_task(self, text: str) -> None:
        assert self._adapter is not None

        parser = TreeParser()
        tree = parser.parse(text)

        self.query_one(TreeView).init_tree(tree.description)
        self.query_one("#output-content", Markdown).update("*Running…*")
        self._update_status("running")

        # Fresh queue for this run
        self._adapter.reset_queue()
        self._adapter_task = asyncio.create_task(self._adapter.run())

        executor = TreeExecutor(
            self._model,
            max_depth=self._max_depth,
            event_queue=self._adapter.queue,
        )

        try:
            result = await executor.execute(tree)
            self.query_one("#output-content", Markdown).update(result)
            total, done, errors = self.query_one(TreeView).stats()
            self._update_status(f"done — {done}/{total} nodes · {errors} errors")
        except Exception as exc:
            self.query_one("#output-content", Markdown).update(
                f"**Error:** {exc}"
            )
            self._update_status(f"error: {exc}")
        finally:
            self._adapter.stop()

    def _update_status(self, msg: str) -> None:
        try:
            self.sub_title = f"{self._model}  depth={self._max_depth}  [{msg}]"
        except Exception:
            pass
