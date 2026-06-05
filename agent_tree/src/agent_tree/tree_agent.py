"""create_tree_agent() — top-level entry point for building tree-capable agents.

Wraps create_deep_agent() with TreeMiddleware injected at the appropriate
depth, producing agents that can recursively spawn tree sub-agents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from deepagents import create_deep_agent
from deepagents.backends.protocol import BackendProtocol, BackendFactory
from deepagents.middleware.filesystem import FilesystemMiddleware, FilesystemPermission

from agent_tree.tree_middleware import TreeMiddleware

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph
    from langgraph.checkpoint.base import BaseCheckpointSaver

DEFAULT_TREE_SYSTEM_PROMPT = """You are a tree-based analysis agent. Your job is to handle your assigned
task, using sub-agents (the `task` tool) to delegate subtasks when appropriate.

Key behavior:
- Decompose your task into independent subtasks when it improves efficiency
- Launch sub-agents in parallel when their tasks don't depend on each other
- Each sub-agent returns a single result — synthesize their outputs
- Use filesystem tools (read_file, write_file, glob, grep) to work with code
- Be thorough but concise in your final summary"""


def create_tree_agent(
    model: str | BaseChatModel,
    *,
    tools: list[BaseTool] | None = None,
    backend: BackendProtocol | BackendFactory | None = None,
    max_depth: int = 3,
    current_depth: int = 0,
    system_prompt: str | None = None,
    permissions: list[FilesystemPermission] | None = None,
    checkpointer: "BaseCheckpointSaver | None" = None,
) -> "CompiledStateGraph":
    """Create a tree-capable agent that can recursively spawn sub-agents.

    The agent at `current_depth` gets a `task` tool if current_depth < max_depth.
    The task tool creates child agents at depth+1 with their own TreeMiddleware.

    Args:
        model: Model string or BaseChatModel instance.
        tools: Tools available to this agent and descendants.
        backend: Backend for filesystem operations.
        max_depth: Maximum tree depth (leaf nodes have no task tool).
        current_depth: Depth of this agent in the tree (0 = root).
        system_prompt: Custom system prompt.
        permissions: Filesystem permission rules.
        checkpointer: LangGraph checkpointer for state persistence.

    Returns:
        A compiled LangGraph StateGraph.
    """
    from deepagents.backends.state import StateBackend

    resolved_backend = backend or StateBackend()
    resolved_tools = list(tools or [])

    middleware: list[Any] = [
        FilesystemMiddleware(
            backend=resolved_backend,
            _permissions=permissions or [],
        ),
        TreeMiddleware(
            depth=current_depth,
            max_depth=max_depth,
            model=model,
            tools=resolved_tools,
            backend=resolved_backend,
        ),
    ]

    prompt = system_prompt or DEFAULT_TREE_SYSTEM_PROMPT
    if current_depth >= max_depth:
        prompt += "\n\nYou are a leaf node. You do not have the task tool. Complete your task directly."

    return create_deep_agent(
        model=model,
        tools=resolved_tools,
        middleware=middleware,
        system_prompt=prompt,
        backend=resolved_backend,
        name=f"tree-agent-L{current_depth}",
        checkpointer=checkpointer,
    )
