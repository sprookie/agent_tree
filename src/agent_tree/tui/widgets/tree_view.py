from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

NodeStatus = Literal["pending", "running", "done", "error"]

_ICON = {
    "pending": ("○", "dim"),
    "running": ("◷", "yellow"),
    "done": ("✓", "green"),
    "error": ("✗", "red"),
}

_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


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
    """Live tree progress widget with spinner animation for running nodes."""

    DEFAULT_CSS = """
    TreeView {
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._root: NodeState | None = None
        self._node_states: dict[tuple[int, ...], NodeState] = {}
        self._tick: int = 0

    def compose(self) -> ComposeResult:
        yield Static(Text("(waiting for task…)", style="dim"), id="tree-content")

    def on_mount(self) -> None:
        self.set_interval(0.12, self._tick_spinner)

    def _tick_spinner(self) -> None:
        if self._has_running():
            self._tick = (self._tick + 1) % len(_SPINNER_FRAMES)
            self._refresh_display()

    def _has_running(self) -> bool:
        return any(n.status == "running" for n in self._node_states.values())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self._root = None
        self._node_states = {}
        try:
            self.query_one("#tree-content", Static).update(
                Text("(waiting for task…)", style="dim")
            )
        except Exception:
            pass

    def init_tree(self, root_description: str) -> None:
        self._root = None
        self._node_states = {}
        root = NodeState(node_path=(), description=root_description, depth=0)
        self._root = root
        self._node_states[()] = root
        self._refresh_display()

    def upsert_node(
        self,
        node_path: tuple[int, ...],
        description: str,
        status: NodeStatus,
        elapsed: float | None = None,
        error: str | None = None,
    ) -> None:
        if node_path not in self._node_states:
            depth = len(node_path)
            node = NodeState(node_path=node_path, description=description, depth=depth)
            self._node_states[node_path] = node
            parent_path = node_path[:-1]
            if parent_path in self._node_states:
                parent = self._node_states[parent_path]
                if node not in parent.children:
                    parent.children.append(node)

        n = self._node_states[node_path]
        n.status = status
        n.description = description
        n.elapsed = elapsed
        n.error = error
        self._refresh_display()

    def stats(self) -> tuple[int, int, int]:
        """Return (total, done, error) node counts."""
        nodes = list(self._node_states.values())
        return len(nodes), sum(1 for n in nodes if n.status == "done"), sum(1 for n in nodes if n.status == "error")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _refresh_display(self) -> None:
        if self._root is None:
            return
        rich_text = Text()
        self._render_node(self._root, rich_text, prefix="", is_last=True)
        try:
            self.query_one("#tree-content", Static).update(rich_text)
        except Exception:
            pass

    def _render_node(
        self, node: NodeState, out: Text, prefix: str, is_last: bool
    ) -> None:
        icon_char, icon_style = _ICON[node.status]
        if node.status == "running":
            icon_char = _SPINNER_FRAMES[self._tick]

        connector = "└ " if is_last else "├ "
        label = f"L{node.depth}" if node.depth > 0 else "root"
        desc = node.description[:60] + "…" if len(node.description) > 60 else node.description

        if node.elapsed is not None:
            timing = f" [{node.elapsed:.1f}s]"
        elif node.status == "running":
            timing = " [running…]"
        else:
            timing = ""

        if node.depth == 0:
            out.append(f"{icon_char} ", style=icon_style)
            out.append(desc, style="bold")
            out.append(timing, style="dim")
        else:
            out.append(prefix + connector, style="dim")
            out.append(f"{icon_char} ", style=icon_style)
            out.append(f"{label} · ", style="dim")
            out.append(desc)
            out.append(timing, style="dim")

        if node.status == "error" and node.error:
            out.append(f"  ← {node.error[:40]}", style="red")

        out.append("\n")

        child_prefix = prefix + ("  " if is_last else "│ ")
        for i, child in enumerate(node.children):
            self._render_node(child, out, child_prefix, i == len(node.children) - 1)
