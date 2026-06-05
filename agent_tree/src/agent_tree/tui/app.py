"""TreeApp — main Textual application for Agent Tree."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Footer, Header, Static

from agent_tree.tree_parser import TreeNode, TreeParser
from agent_tree.tree_executor import TreeExecutor
from agent_tree.tui.adapter import TreeUIAdapter
from agent_tree.tui.widgets.tree_view import TreeView
from agent_tree.tui.widgets.task_input import TaskInput

if TYPE_CHECKING:
    pass


class TreeApp(App):
    """Textual application for Agent Tree."""

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+r", "run", "Run Tree"),
        ("ctrl+n", "new", "New Task"),
    ]

    def __init__(self, model: str = "deepseek-reasoner", max_depth: int = 3) -> None:
        super().__init__()
        self._model = model
        self._max_depth = max_depth
        self._tree: TreeNode | None = None
        self._running = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static("Agent Tree — Multi-Level Task Decomposition", id="title"),
            Static("Enter your task tree below. Ctrl+R to run, Ctrl+Q to quit:", id="subtitle"),
            TaskInput(id="task-input"),
            id="top-section",
        )
        yield Footer()

    def action_run(self) -> None:
        if self._running:
            return
        input_widget = self.query_one("#task-input", TaskInput)
        text = input_widget.input_text
        parser = TreeParser()
        tree = parser.parse(text)
        if not tree:
            self.notify("No @tree block found. Use @tree syntax.", severity="warning")
            return
        self._tree = tree
        self._running = True
        self.run_worker(self._execute_tree(tree), exclusive=True)

    def action_new(self) -> None:
        if self._running:
            self.notify("Cannot clear while running.", severity="warning")
            return
        input_widget = self.query_one("#task-input", TaskInput)
        textarea = input_widget.query_one("#task-textarea")
        textarea.text = ""

    async def _execute_tree(self, tree: TreeNode) -> None:
        from deepagents.backends.state import StateBackend
        from langchain_openai import ChatOpenAI

        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        model = ChatOpenAI(
            model="deepseek-reasoner",
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            temperature=0,
        )
        backend = StateBackend()
        executor = TreeExecutor(model=model, tools=[], backend=backend, max_depth=self._max_depth)

        top = self.query_one("#top-section", Vertical)
        tree_view = TreeView(tree)
        await top.mount(tree_view)

        adapter = TreeUIAdapter(tree_view=tree_view)
        executor.on_node_start(adapter.on_node_start)
        executor.on_node_complete(adapter.on_node_complete)

        try:
            result = await executor.execute(tree)
            tree_view.set_summary(result)
            self.notify("Tree execution complete!", severity="information")
        except Exception as e:
            tree_view.set_summary(f"Error: {e}")
            self.notify(f"Execution failed: {e}", severity="error")
        finally:
            self._running = False
