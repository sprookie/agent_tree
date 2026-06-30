import asyncio
import pytest

from agent_tree.tui.app import TreeApp
from agent_tree.tui.widgets import TreeView, TaskInput
from textual.widgets import Markdown


@pytest.mark.asyncio
async def test_tui_widgets_mount():
    app = TreeApp(model="openai:deepseek-v4-pro", max_depth=3)
    async with app.run_test(headless=True, size=(120, 40)) as pilot:
        assert app.query_one(TreeView) is not None
        assert app.query_one(TaskInput) is not None
        assert app.query_one("#output-content", Markdown) is not None
        await pilot.press("ctrl+q")


@pytest.mark.asyncio
async def test_tui_tree_view_nodes():
    app = TreeApp(model="openai:deepseek-v4-pro", max_depth=3)
    async with app.run_test(headless=True, size=(120, 40)) as pilot:
        tv = app.query_one(TreeView)

        tv.init_tree("root task")
        tv.upsert_node((), "root task", "running")
        tv.upsert_node((0,), "child A", "running")
        tv.upsert_node((1,), "child B", "done", elapsed=2.5)
        await pilot.pause(0.1)

        total, done, errors = tv.stats()
        assert total == 3
        assert done == 1
        assert errors == 0

        await pilot.press("ctrl+q")


@pytest.mark.asyncio
async def test_tui_tree_view_error_state():
    app = TreeApp(model="openai:deepseek-v4-pro", max_depth=3)
    async with app.run_test(headless=True, size=(120, 40)) as pilot:
        tv = app.query_one(TreeView)

        tv.init_tree("root")
        tv.upsert_node((), "root", "running")
        tv.upsert_node((0,), "failing child", "error", error="connection timeout")
        await pilot.pause(0.1)

        _, _, errors = tv.stats()
        assert errors == 1

        await pilot.press("ctrl+q")


@pytest.mark.asyncio
async def test_tui_spinner_animates():
    app = TreeApp(model="openai:deepseek-v4-pro", max_depth=3)
    async with app.run_test(headless=True, size=(120, 40)) as pilot:
        tv = app.query_one(TreeView)
        tv.init_tree("root")
        tv.upsert_node((), "root", "running")

        tick_before = tv._tick
        await pilot.pause(0.5)
        tick_after = tv._tick
        assert tick_after != tick_before

        await pilot.press("ctrl+q")


@pytest.mark.asyncio
async def test_tui_reset_clears_tree():
    app = TreeApp(model="openai:deepseek-v4-pro", max_depth=3)
    async with app.run_test(headless=True, size=(120, 40)) as pilot:
        tv = app.query_one(TreeView)
        tv.init_tree("root")
        tv.upsert_node((), "root", "done", elapsed=1.0)

        tv.reset()
        await pilot.pause(0.1)
        assert tv._root is None
        assert tv._node_states == {}

        await pilot.press("ctrl+q")


@pytest.mark.asyncio
async def test_tui_clear_action():
    app = TreeApp(model="openai:deepseek-v4-pro", max_depth=3)
    async with app.run_test(headless=True, size=(120, 40)) as pilot:
        tv = app.query_one(TreeView)
        tv.init_tree("root")
        tv.upsert_node((), "root", "done", elapsed=5.0)

        await pilot.press("ctrl+l")
        await pilot.pause(0.1)
        assert tv._root is None

        await pilot.press("ctrl+q")
