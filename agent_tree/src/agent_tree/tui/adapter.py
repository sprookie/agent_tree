"""TreeUIAdapter — bridges TreeExecutor events to TUI widgets."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from agent_tree.tree_parser import TreeNode

if TYPE_CHECKING:
    from agent_tree.tui.widgets.tree_view import TreeView


class TreeUIAdapter:
    """Receives callbacks from TreeExecutor and updates TUI widgets."""

    def __init__(self, tree_view: "TreeView") -> None:
        self._tree_view = tree_view
        self._start_times: dict[str, float] = {}

    def on_node_start(self, node: TreeNode, result: str | None = None, error: Exception | None = None) -> None:
        self._start_times[node.description] = time.monotonic()
        self._tree_view.update_node(node.description, "running")

    def on_node_complete(self, node: TreeNode, result: str | None = None, error: Exception | None = None) -> None:
        elapsed = 0.0
        if node.description in self._start_times:
            elapsed = time.monotonic() - self._start_times[node.description]
            del self._start_times[node.description]
        if error:
            self._tree_view.update_node(node.description, "error", elapsed=elapsed)
        else:
            self._tree_view.update_node(node.description, "done", elapsed=elapsed)
