from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


NodeStatus = Literal["pending", "running", "done", "error"]

_ICON = {
    "pending": "○",
    "running": "◷",
    "done": "✓",
    "error": "✗",
}

_STATUS_CLASS = {
    "pending": "pending",
    "running": "running",
    "done": "done",
    "error": "error",
}


@dataclass
class NodeState:
    node_path: tuple[int, ...]
    description: str
    status: NodeStatus = "pending"
    elapsed: float | None = None
    error: str | None = None
    depth: int = 0
    children: list[NodeState] = field(default_factory=list)


class TreeView(Widget):
    """Renders a live tree of agent node statuses."""

    DEFAULT_CSS = """
    TreeView {
        height: auto;
        min-height: 3;
        padding: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._root: NodeState | None = None
        self._nodes: dict[tuple[int, ...], NodeState] = {}

    def compose(self) -> ComposeResult:
        yield Static("(waiting for task…)", id="tree-content")

    def init_tree(self, root_description: str) -> None:
        root = NodeState(node_path=(), description=root_description, depth=0)
        self._root = root
        self._nodes[()] = root
        self._refresh()

    def upsert_node(
        self,
        node_path: tuple[int, ...],
        description: str,
        status: NodeStatus,
        elapsed: float | None = None,
        error: str | None = None,
    ) -> None:
        if node_path not in self._nodes:
            depth = len(node_path)
            node = NodeState(
                node_path=node_path,
                description=description,
                depth=depth,
            )
            self._nodes[node_path] = node
            # Attach to parent
            parent_path = node_path[:-1]
            if parent_path in self._nodes:
                self._nodes[parent_path].children.append(node)
            elif parent_path == () and self._root is None:
                self._root = node

        n = self._nodes[node_path]
        n.status = status
        n.description = description
        n.elapsed = elapsed
        n.error = error
        self._refresh()

    def _refresh(self) -> None:
        if self._root is None:
            return
        lines = self._render_node(self._root, prefix="", is_last=True)
        content = "\n".join(lines)
        try:
            static = self.query_one("#tree-content", Static)
            static.update(content)
        except Exception:
            pass

    def _render_node(self, node: NodeState, prefix: str, is_last: bool) -> list[str]:
        icon = _ICON[node.status]
        connector = "└ " if is_last else "├ "
        label = f"L{node.depth}" if node.depth > 0 else "root"
        desc = node.description[:55] + "…" if len(node.description) > 55 else node.description

        timing = ""
        if node.elapsed is not None:
            timing = f" [{node.elapsed:.1f}s]"
        elif node.status == "running":
            timing = " [running]"

        if node.status == "error" and node.error:
            timing += f" ✗ {node.error[:30]}"

        if node.depth == 0:
            line = f"{icon} {desc}{timing}"
        else:
            line = f"{prefix}{connector}{icon} {label} · {desc}{timing}"

        lines = [line]

        child_prefix = prefix + ("  " if is_last else "│ ")
        for i, child in enumerate(node.children):
            child_is_last = i == len(node.children) - 1
            lines.extend(self._render_node(child, child_prefix, child_is_last))

        return lines
