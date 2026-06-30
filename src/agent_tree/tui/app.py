from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Label, Static
from textual.containers import Vertical, ScrollableContainer

from ..tree_executor import TreeExecutor
from ..tree_parser import TreeParser
from .adapter import TreeUIAdapter
from .widgets import TaskInput, TreeView


class TreeApp(App):
    """Agent Tree TUI application."""

    CSS_PATH = Path(__file__).parent / "styles.tcss"
    TITLE = "agent-tree"
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+t", "focus_tree", "Tree"),
        ("ctrl+i", "focus_input", "Input"),
    ]

    def __init__(
        self,
        model: str = "anthropic:claude-sonnet-4-6",
        max_depth: int = 3,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._model = model
        self._max_depth = max_depth
        self._tree_view: TreeView | None = None
        self._adapter: TreeUIAdapter | None = None
        self._executor_task: asyncio.Task | None = None
        self._adapter_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="body"):
            with ScrollableContainer(id="tree-panel"):
                yield Label("Tree Progress", id="tree-label")
                tv = TreeView()
                self._tree_view = tv
                yield tv
            with ScrollableContainer(id="output-panel"):
                yield Label("Final Report")
                yield Static("", id="output-content")
            with Vertical(id="input-panel"):
                yield Label("Task  (Ctrl+Enter to submit)")
                yield TaskInput()
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = f"depth={self._max_depth} · {self._model}"
        if self._tree_view:
            self._adapter = TreeUIAdapter(self._tree_view)
        self.query_one(TaskInput).focus()

    def action_focus_tree(self) -> None:
        self.query_one("#tree-panel").focus()

    def action_focus_input(self) -> None:
        self.query_one(TaskInput).focus()

    def action_submit_task(self) -> None:
        task_input = self.query_one(TaskInput)
        text = task_input.get_text().strip()
        if not text:
            return
        task_input.clear()
        if self._executor_task and not self._executor_task.done():
            self._executor_task.cancel()
        if self._adapter_task and not self._adapter_task.done():
            self._adapter_task.cancel()
        self._executor_task = asyncio.create_task(self._run_task(text))

    async def _run_task(self, text: str) -> None:
        assert self._adapter is not None
        assert self._tree_view is not None

        parser = TreeParser()
        tree = parser.parse(text)

        self._tree_view.init_tree(tree.description)
        output = self.query_one("#output-content", Static)
        output.update("Running…")

        self._adapter_task = asyncio.create_task(self._adapter.run())

        executor = TreeExecutor(
            self._model,
            max_depth=self._max_depth,
            event_queue=self._adapter.queue,
        )

        try:
            result = await executor.execute(tree)
            output.update(result)
        except Exception as exc:
            output.update(f"[red]Error: {exc}[/red]")
        finally:
            self._adapter.stop()
