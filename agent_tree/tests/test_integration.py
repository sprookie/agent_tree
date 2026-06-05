"""Integration tests for the full tree execution flow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_tree.tree_parser import TreeParser, TreeNode
from agent_tree.tree_executor import TreeExecutor


def test_parse_and_execute_workflow():
    """Verify the full parse -> execute pipeline structurally."""
    tree_text = """@tree
root analysis
  - sub task A
    - leaf A1
    - leaf A2
  - sub task B
    - leaf B1"""

    parser = TreeParser()
    tree = parser.parse(tree_text)
    assert tree is not None
    assert len(tree.children) == 2

    child_a = tree.children[0]
    assert child_a.description == "sub task A"
    assert len(child_a.children) == 2

    child_b = tree.children[1]
    assert child_b.description == "sub task B"
    assert len(child_b.children) == 1


@pytest.mark.asyncio
async def test_executor_event_callbacks():
    """Verify on_node_start and on_node_complete callbacks fire."""
    start_events = []
    complete_events = []

    async def fake_ainvoke(state, config=None):
        return {"messages": [MagicMock(text="result")]}

    with patch("agent_tree.tree_executor.create_tree_agent") as mock_create:
        mock_agent = MagicMock()
        mock_agent.ainvoke = fake_ainvoke
        mock_create.return_value = mock_agent

        executor = TreeExecutor(model=MagicMock(), tools=[], backend=MagicMock(), max_depth=3)
        executor.on_node_start(lambda n, r, e: start_events.append(n.description))
        executor.on_node_complete(lambda n, r, e: complete_events.append(n.description))

        root = TreeNode(description="test task")
        await executor.execute(root)

    assert "test task" in start_events
    assert "test task" in complete_events
    assert len(start_events) == 1
    assert len(complete_events) == 1


@pytest.mark.asyncio
async def test_executor_nested_tree_callbacks():
    """Verify event callbacks fire for all nodes in a nested tree."""
    root = TreeNode(description="root task")
    child = TreeNode(description="child task", depth=1, parent=root)
    root.children.append(child)

    started = []
    completed = []

    async def fake_ainvoke(state, config=None):
        content = state["messages"][0].content
        return {"messages": [MagicMock(text=f"result for {content}")]}

    with patch("agent_tree.tree_executor.create_tree_agent") as mock_create:
        mock_agent = MagicMock()
        mock_agent.ainvoke = fake_ainvoke
        mock_create.return_value = mock_agent

        executor = TreeExecutor(model=MagicMock(), tools=[], backend=MagicMock(), max_depth=3)
        executor._summarize = AsyncMock(return_value="summary of children")
        executor.on_node_start(lambda n, r, e: started.append(n.description))
        executor.on_node_complete(lambda n, r, e: completed.append(n.description))

        await executor.execute(root)

    assert "root task" in started
    assert "child task" in started
    assert "root task" in completed
    assert "child task" in completed
    assert len(started) == 2
    assert len(completed) == 2
