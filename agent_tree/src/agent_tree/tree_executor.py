"""TreeExecutor — bottom-up execution engine for tree task structures.

Executes leaves first (in parallel), collects results in child order,
and summarizes upward through the tree.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from deepagents.backends.protocol import BackendProtocol

from agent_tree.tree_parser import TreeNode

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

create_tree_agent = None  # Lazy-loaded from agent_tree.tree_agent on first use


SUMMARY_PROMPT = """You are synthesizing results from sub-tasks in a tree analysis.

Your parent task was: {parent_description}

Below are the results from your sub-tasks. Synthesize them into a single
concise report for your parent. Include key findings, notable details,
and connections between sub-results. Be thorough but concise.

Sub-task results:

{child_results}

Synthesized report:"""


class TreeExecutor:
    """Execute a TreeNode structure bottom-up.

    Leaves are executed first in parallel. Each parent waits for all children,
    then synthesizes their results into a summary via an LLM call.
    """

    def __init__(
        self,
        *,
        model: str | BaseChatModel,
        tools: list[BaseTool],
        backend: BackendProtocol,
        max_depth: int = 3,
    ) -> None:
        self._model = model
        self._tools = list(tools)
        self._backend = backend
        self.max_depth = max_depth
        self._event_callbacks: list[tuple[str, Any]] = []

    def on_node_start(self, callback) -> None:
        """Register callback for node execution start: callback(node, result, error)."""
        self._event_callbacks.append(("start", callback))

    def on_node_complete(self, callback) -> None:
        """Register callback for node completion: callback(node, result, error)."""
        self._event_callbacks.append(("complete", callback))

    async def execute(self, tree: TreeNode) -> str:
        """Execute a task tree bottom-up and return the root's result."""
        return await self._execute_node(tree)

    async def _execute_node(self, node: TreeNode) -> str:
        """Execute a node: children first (parallel), then synthesize."""
        self._emit("start", node)

        if not node.children:
            result = await self._run_leaf_agent(node)
            self._emit("complete", node, result, None)
            return result

        child_tasks = [self._execute_node(child) for child in node.children]
        child_results = await asyncio.gather(*child_tasks, return_exceptions=True)

        processed_results: list[str] = []
        for child, result in zip(node.children, child_results):
            if isinstance(result, BaseException):
                processed_results.append(f"[ERROR from '{child.description}': {result}]")
            else:
                processed_results.append(str(result))

        summary = await self._summarize(node.description, processed_results)
        self._emit("complete", node, summary, None)
        return summary

    async def _run_leaf_agent(self, node: TreeNode) -> str:
        """Run a leaf node agent at max_depth (no task tool)."""
        global create_tree_agent
        if create_tree_agent is None:
            from agent_tree.tree_agent import create_tree_agent as _cta
            create_tree_agent = _cta
        agent = create_tree_agent(
            model=self._model,
            tools=self._tools,
            backend=self._backend,
            max_depth=self.max_depth,
            current_depth=self.max_depth,
        )
        result = await agent.ainvoke({"messages": [HumanMessage(content=node.description)]})
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.text and msg.text.strip():
                return msg.text
        return "(leaf agent returned no result)"

    async def _summarize(self, parent_description: str, child_results: list[str]) -> str:
        """Use an LLM call to summarize child results."""
        child_text = "\n\n---\n\n".join(
            f"### Subtask {i+1}\n{r}" for i, r in enumerate(child_results)
        )
        prompt = SUMMARY_PROMPT.format(
            parent_description=parent_description, child_results=child_text
        )
        agent = self._build_summary_agent()
        result = await agent.ainvoke({
            "messages": [
                SystemMessage(content=prompt),
                HumanMessage(content="Synthesize the sub-task results."),
            ],
        })
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.text and msg.text.strip():
                return msg.text
        return "\n\n".join(child_results)

    def _build_summary_agent(self) -> "CompiledStateGraph":
        """Build a minimal deepagent for summarization."""
        from deepagents import create_deep_agent
        return create_deep_agent(
            model=self._model,
            tools=[],
            middleware=[],
            name="tree-summarizer",
            system_prompt="You are a concise summarizer. Synthesize sub-task results.",
        )

    def _emit(self, event: str, node: TreeNode, result: str | None = None, error: Exception | None = None) -> None:
        for etype, cb in self._event_callbacks:
            if etype == event:
                cb(node, result, error)
