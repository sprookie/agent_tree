"""TreeView widget — renders tree execution progress."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Vertical
from textual.widgets import Static

from agent_tree.tree_parser import TreeNode

if TYPE_CHECKING:
    from textual.app import ComposeResult


class TreeView(Vertical):
    """Renders a tree of task nodes with execution status."""

    DEFAULT_CSS = """
    TreeView {
        height: auto;
        padding: 1 2;
        margin: 1 0;
        border: solid $primary;
    }
    TreeView .tree-header {
        color: $text;
        text-style: bold;
        padding: 0 0 1 0;
    }
    TreeView .tree-summary {
        color: $text-muted;
        margin: 1 0 0 0;
        border-top: dashed $primary;
        padding: 1 0 0 0;
    }
    """

    def __init__(self, tree: TreeNode, **kwargs) -> None:
        super().__init__(**kwargs)
        self._tree = tree
        self._statuses: dict[str, str] = {}

    def compose(self) -> "ComposeResult":
        yield Static("Task Tree", classes="tree-header")
        yield Static(self._render_static(self._tree, indent=0), id="tree-content")
        yield Static("Waiting for execution...", id="tree-summary", classes="tree-summary")

    def _render_static(self, node: TreeNode, indent: int = 0) -> str:
        lines = [f"{'  ' * indent}○ {node.description}"]
        for child in node.children:
            lines.append(self._render_static(child, indent + 1))
        return "\n".join(lines)

    def update_node(self, description: str, status: str, result: str = "", elapsed: float = 0) -> None:
        """Update a node's status by matching its description."""
        self._statuses[description] = status
        self.refresh()

    def refresh_content(self) -> None:
        tree_widget = self.query_one("#tree-content", Static)
        tree_widget.update(self._render_live(self._tree))

    def _render_live(self, node: TreeNode, indent: int = 0) -> str:
        prefix = "  " * indent
        icon_map = {"pending": "○", "running": "◷", "done": "✓", "error": "✗"}
        icon = icon_map.get(self._statuses.get(node.description, "pending"), "○")
        elapsed_str = ""
        lines = [f"{prefix}{icon} {node.description}{elapsed_str}"]
        for child in node.children:
            lines.append(self._render_live(child, indent + 1))
        return "\n".join(lines)

    def set_summary(self, text: str) -> None:
        summary_widget = self.query_one("#tree-summary", Static)
        summary_widget.update(text)
