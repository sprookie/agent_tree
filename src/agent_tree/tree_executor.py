from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Literal

from deepagents.backends.protocol import BackendProtocol
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool

from .tree_agent import _DEFAULT_LEAF_MODEL, _resolve_model, create_tree_agent
from .tree_node import TreeNode


@dataclass
class NodeEvent:
    node_path: tuple[int, ...]
    status: Literal["pending", "running", "done", "error"]
    description: str = ""
    result: str | None = None
    elapsed: float | None = None
    error: str | None = None


class TreeExecutor:
    """Execute a TreeNode hierarchy bottom-up with parallel siblings.

    Events are emitted to ``event_queue`` (if provided) so that a TUI or
    other consumer can track per-node progress in real time.
    """

    def __init__(
        self,
        model: str | BaseChatModel,
        *,
        leaf_model: str | BaseChatModel | None = None,
        tools: list[BaseTool] | None = None,
        backend: BackendProtocol | None = None,
        max_depth: int = 3,
        event_queue: asyncio.Queue[NodeEvent] | None = None,
    ) -> None:
        self.model = _resolve_model(model)
        self.leaf_model = _resolve_model(leaf_model if leaf_model is not None else _DEFAULT_LEAF_MODEL)
        self.tools = tools or []
        self.backend = backend
        self.max_depth = max_depth
        self.event_queue = event_queue

    async def execute(self, tree: TreeNode) -> str:
        """Execute the tree and return the root summary."""
        return await self._execute_node(tree, remaining_depth=self.max_depth)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _execute_node(self, node: TreeNode, remaining_depth: int) -> str:
        await self._emit(NodeEvent(
            node_path=node.node_path,
            status="running",
            description=node.description,
        ))
        start = time.monotonic()
        try:
            if node.is_leaf():
                result = await self._run_leaf(node, remaining_depth)
            else:
                # Execute all children in parallel, then summarize
                child_results = await asyncio.gather(
                    *[
                        self._execute_node(child, remaining_depth - 1)
                        for child in node.children
                    ]
                )
                result = await self._summarize(node.description, list(child_results))

            elapsed = time.monotonic() - start
            await self._emit(NodeEvent(
                node_path=node.node_path,
                status="done",
                description=node.description,
                result=result,
                elapsed=elapsed,
            ))
            return result

        except Exception as exc:
            elapsed = time.monotonic() - start
            await self._emit(NodeEvent(
                node_path=node.node_path,
                status="error",
                description=node.description,
                error=str(exc),
                elapsed=elapsed,
            ))
            raise

    async def _run_leaf(self, node: TreeNode, remaining_depth: int) -> str:
        # Leaf nodes use leaf_model for actual task execution
        agent = create_tree_agent(
            self.leaf_model,
            leaf_model=self.leaf_model,
            tools=self.tools,
            backend=self.backend,
            max_depth=remaining_depth,
        )
        state = await agent.ainvoke({"messages": [HumanMessage(content=node.description)]})
        return self._extract_text(state)

    async def _summarize(self, parent_task: str, child_results: list[str]) -> str:
        numbered = "\n\n".join(
            f"Sub-task {i + 1}:\n{r}" for i, r in enumerate(child_results)
        )
        prompt = (
            f"You are synthesising results for the task: {parent_task}\n\n"
            f"Results from sub-tasks:\n{numbered}\n\n"
            "Write a concise, comprehensive summary that integrates all findings."
        )
        # Synthesis uses root model (smarter, better at integration)
        agent = create_tree_agent(
            self.model,
            leaf_model=self.leaf_model,
            tools=[],
            backend=self.backend,
            max_depth=1,
        )
        state = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
        return self._extract_text(state)

    @staticmethod
    def _extract_text(state: dict) -> str:
        for msg in reversed(state.get("messages", [])):
            content = getattr(msg, "content", None)
            tool_calls = getattr(msg, "tool_calls", None)
            if content and isinstance(content, str) and not tool_calls:
                return content
        return "(no result)"

    async def _emit(self, event: NodeEvent) -> None:
        if self.event_queue is not None:
            await self.event_queue.put(event)
