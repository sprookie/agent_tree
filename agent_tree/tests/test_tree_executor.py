import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage
from agent_tree.tree_parser import TreeNode
from agent_tree.tree_executor import TreeExecutor


def make_leaf(desc: str, depth: int = 1) -> TreeNode:
    return TreeNode(description=desc, depth=depth)


def make_node(desc: str, *children: TreeNode) -> TreeNode:
    n = TreeNode(description=desc, depth=0)
    for child in children:
        child.parent = n
        child.depth = n.depth + 1
        n.children.append(child)
    return n


def test_init():
    e = TreeExecutor(model=MagicMock(), tools=[], backend=MagicMock(), max_depth=3)
    assert e.max_depth == 3


@pytest.mark.asyncio
async def test_single_node():
    root = TreeNode(description="just one task")
    with patch("agent_tree.tree_executor.create_tree_agent") as mock_create:
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="done")]})
        mock_create.return_value = mock_agent
        e = TreeExecutor(model=MagicMock(), tools=[], backend=MagicMock(), max_depth=3)
        result = await e.execute(root)
    assert result == "done"


@pytest.mark.asyncio
async def test_flat_tree_parallel():
    """A root with 2 leaf children: leaves run in parallel, then root summarizes."""
    leaf1 = make_leaf("task 1")
    leaf2 = make_leaf("task 2")
    root = make_node("root", leaf1, leaf2)
    call_order = []

    async def fake_ainvoke(state, config=None):
        content = state["messages"][0].content
        call_order.append(content)
        return {"messages": [AIMessage(content="leaf result")]}

    with patch("agent_tree.tree_executor.create_tree_agent") as mock_create:
        mock_agent = MagicMock()
        mock_agent.ainvoke = fake_ainvoke
        mock_create.return_value = mock_agent
        e = TreeExecutor(model=MagicMock(), tools=[], backend=MagicMock(), max_depth=3)
        e._summarize = AsyncMock(return_value="summary")
        result = await e.execute(root)
    assert result == "summary"
    assert len(call_order) == 2  # 2 leaves in parallel


@pytest.mark.asyncio
async def test_event_callbacks():
    start_events = []
    complete_events = []
    root = TreeNode(description="test")

    with patch("agent_tree.tree_executor.create_tree_agent") as mock_create:
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="done")]})
        mock_create.return_value = mock_agent
        e = TreeExecutor(model=MagicMock(), tools=[], backend=MagicMock(), max_depth=3)
        e.on_node_start(lambda n, r, e: start_events.append(n.description))
        e.on_node_complete(lambda n, r, e: complete_events.append(n.description))
        await e.execute(root)
    assert "test" in start_events
    assert "test" in complete_events
