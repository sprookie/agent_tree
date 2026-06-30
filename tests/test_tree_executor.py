import asyncio
import pytest

from agent_tree import NodeEvent, TreeExecutor, TreeNode, TreeParser


@pytest.mark.asyncio
async def test_executor_emits_events():
    """TreeExecutor should emit running/done events for each node."""
    tree = TreeNode(
        description="root",
        node_path=(),
        children=[
            TreeNode(description="child A", node_path=(0,)),
            TreeNode(description="child B", node_path=(1,)),
        ],
    )

    queue: asyncio.Queue[NodeEvent] = asyncio.Queue()
    events: list[NodeEvent] = []

    # Patch _run_leaf to avoid real LLM calls
    executor = TreeExecutor(
        "anthropic:claude-haiku-4-5-20251001",
        max_depth=2,
        event_queue=queue,
    )

    async def fake_run_leaf(node, remaining_depth):
        return f"result for {node.description}"

    async def fake_summarize(task, results):
        return f"summary of: {', '.join(results)}"

    executor._run_leaf = fake_run_leaf
    executor._summarize = fake_summarize

    result = await executor.execute(tree)

    # Drain queue
    while not queue.empty():
        events.append(queue.get_nowait())

    statuses = [(e.node_path, e.status) for e in events]

    # Both children and root should have running + done events
    assert ((), "running") in statuses
    assert ((), "done") in statuses
    assert ((0,), "running") in statuses
    assert ((0,), "done") in statuses
    assert ((1,), "running") in statuses
    assert ((1,), "done") in statuses

    assert "result for child A" in result or "summary" in result


@pytest.mark.asyncio
async def test_executor_single_leaf():
    """Single leaf node (no children) should call _run_leaf directly."""
    tree = TreeNode(description="simple task", node_path=())

    queue: asyncio.Queue[NodeEvent] = asyncio.Queue()
    executor = TreeExecutor("anthropic:claude-haiku-4-5-20251001", max_depth=2, event_queue=queue)

    async def fake_run_leaf(node, remaining_depth):
        return "leaf result"

    executor._run_leaf = fake_run_leaf

    result = await executor.execute(tree)
    assert result == "leaf result"


@pytest.mark.asyncio
async def test_executor_error_emits_error_event():
    tree = TreeNode(description="failing task", node_path=())

    queue: asyncio.Queue[NodeEvent] = asyncio.Queue()
    executor = TreeExecutor("anthropic:claude-haiku-4-5-20251001", max_depth=2, event_queue=queue)

    async def fail_leaf(node, remaining_depth):
        raise RuntimeError("oops")

    executor._run_leaf = fail_leaf

    with pytest.raises(RuntimeError):
        await executor.execute(tree)

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    error_events = [e for e in events if e.status == "error"]
    assert len(error_events) == 1
    assert "oops" in error_events[0].error
