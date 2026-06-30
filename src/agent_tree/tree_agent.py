from __future__ import annotations

import os

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True), override=False)

from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from deepagents.backends.protocol import BackendProtocol
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph


def _resolve_model(model: str | BaseChatModel) -> str | BaseChatModel:
    """Resolve a model string to a BaseChatModel when the endpoint is not OpenAI.

    The new openai SDK defaults to the Responses API (/responses) which many
    third-party OpenAI-compatible providers (DeepSeek, etc.) don't support.
    When OPENAI_API_BASE is set to a non-OpenAI URL we construct the model
    instance explicitly with use_responses_api=False.
    """
    if isinstance(model, BaseChatModel):
        return model

    base_url = os.environ.get("OPENAI_API_BASE", "")
    provider, _, model_id = model.partition(":")
    if provider == "openai" and base_url and "openai.com" not in base_url:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_id or model,
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=base_url,
            use_responses_api=False,
        )
    return model

_TASK_DESCRIPTION = (
    "Delegate a focused sub-task to an independent sub-agent. "
    "The sub-agent works in an isolated context and returns a concise summary. "
    "Use this to decompose complex work into parallel specialised workstreams."
)

_ROOT_SYSTEM_PROMPT = (
    "You are a tree-structured research and analysis agent. "
    "Break complex tasks into focused sub-tasks using the `task` tool. "
    "Each sub-agent works independently and reports back a concise summary. "
    "After all sub-tasks complete, synthesise their results into a comprehensive final answer."
)


def _build_layer(
    model: str | BaseChatModel,
    leaf_model: str | BaseChatModel,
    tools: list[BaseTool],
    backend: BackendProtocol,
    depth: int,
    max_depth: int,
    system_prompt: str | None,
) -> CompiledStateGraph:
    """Recursively build one layer of the agent tree.

    depth >= max_depth  →  leaf agent (uses leaf_model, no task tool)
    depth < max_depth   →  non-leaf agent (uses model, has task tool pointing to depth+1)
    """
    if depth >= max_depth:
        return create_deep_agent(
            leaf_model,
            tools=tools,
            backend=backend,
            name=f"L{depth}-leaf",
        )

    child_graph = _build_layer(model, leaf_model, tools, backend, depth + 1, max_depth, system_prompt=None)

    return create_deep_agent(
        model,
        tools=tools,
        backend=backend,
        subagents=[
            {
                "name": "task",
                "description": _TASK_DESCRIPTION,
                "runnable": child_graph,
            }
        ],
        system_prompt=system_prompt if depth == 0 else None,
        name=f"L{depth}",
    )


_DEFAULT_LEAF_MODEL = "openai:deepseek-v4-flash"


def create_tree_agent(
    model: str | BaseChatModel,
    *,
    leaf_model: str | BaseChatModel | None = None,
    tools: list[BaseTool] | None = None,
    backend: BackendProtocol | None = None,
    max_depth: int = 3,
    system_prompt: str | None = None,
) -> CompiledStateGraph:
    """Create a recursive tree agent.

    Args:
        model: Root/orchestrator model — used for non-leaf agents and synthesis.
            E.g. ``"openai:deepseek-v4-pro"`` or a ``BaseChatModel`` instance.
        leaf_model: Leaf agent model — used for actual task execution at the
            deepest layer.  Defaults to ``"openai:deepseek-v4-flash"`` (faster
            and cheaper).  Pass the same value as ``model`` to disable
            per-layer switching.
        tools: Domain tools available at every layer.
        backend: File-system backend.  Defaults to ``StateBackend()``.
        max_depth: Maximum number of recursive layers.  Agents at
            ``depth == max_depth`` are leaves with no ``task`` tool.
        system_prompt: Optional root-level system prompt override.

    Returns:
        A compiled LangGraph that accepts ``{"messages": [...]}`` input.
    """
    if backend is None:
        backend = StateBackend()
    if system_prompt is None:
        system_prompt = _ROOT_SYSTEM_PROMPT
    resolved = _resolve_model(model)
    resolved_leaf = _resolve_model(leaf_model if leaf_model is not None else _DEFAULT_LEAF_MODEL)
    return _build_layer(resolved, resolved_leaf, tools or [], backend, depth=0, max_depth=max_depth, system_prompt=system_prompt)
