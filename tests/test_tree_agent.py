import pytest
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph

from agent_tree import create_tree_agent


def test_create_tree_agent_returns_graph():
    agent = create_tree_agent("anthropic:claude-haiku-4-5-20251001", max_depth=2)
    assert isinstance(agent, CompiledStateGraph)


def test_create_tree_agent_depth_zero_is_leaf():
    """max_depth=0 should still produce a graph (leaf at root)."""
    agent = create_tree_agent("anthropic:claude-haiku-4-5-20251001", max_depth=0)
    assert isinstance(agent, CompiledStateGraph)


def test_create_tree_agent_max_depth_3():
    agent = create_tree_agent("anthropic:claude-haiku-4-5-20251001", max_depth=3)
    assert isinstance(agent, CompiledStateGraph)


def test_create_tree_agent_with_tools():
    from langchain_core.tools import tool

    @tool
    def dummy_search(query: str) -> str:
        """Search for something."""
        return f"results for {query}"

    agent = create_tree_agent(
        "anthropic:claude-haiku-4-5-20251001",
        tools=[dummy_search],
        max_depth=2,
    )
    assert isinstance(agent, CompiledStateGraph)
