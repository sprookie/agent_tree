import pytest
from unittest.mock import MagicMock
from agent_tree.tree_middleware import TreeMiddleware


def test_tree_middleware_has_tools_when_depth_lt_max():
    mw = TreeMiddleware(depth=0, max_depth=3, model="test-model", tools=[], backend=MagicMock())
    assert len(mw.tools) == 1
    assert mw.tools[0].name == "task"

def test_tree_middleware_no_tools_when_depth_eq_max():
    mw = TreeMiddleware(depth=3, max_depth=3, model="test-model", tools=[], backend=MagicMock())
    assert len(mw.tools) == 0

def test_tree_middleware_no_tools_when_depth_gt_max():
    mw = TreeMiddleware(depth=5, max_depth=3, model="test-model", tools=[], backend=MagicMock())
    assert len(mw.tools) == 0

def test_tree_middleware_depth_properties():
    mw = TreeMiddleware(depth=1, max_depth=3, model="test-model", tools=[], backend=MagicMock())
    assert mw.depth == 1
    assert mw.max_depth == 3

def test_tree_middleware_has_system_prompt_when_depth_lt_max():
    mw = TreeMiddleware(depth=0, max_depth=3, model="test-model", tools=[], backend=MagicMock())
    assert mw.system_prompt is not None

def test_tree_middleware_no_system_prompt_when_leaf():
    mw = TreeMiddleware(depth=3, max_depth=3, model="test-model", tools=[], backend=MagicMock())
    assert mw.system_prompt is None

def test_tree_middleware_tool_has_correct_schema():
    mw = TreeMiddleware(depth=0, max_depth=3, model="test-model", tools=[], backend=MagicMock())
    tool = mw.tools[0]
    assert tool.args_schema is not None
    schema = tool.args_schema.model_json_schema()
    assert "description" in schema.get("properties", {})
    assert "subagent_type" in schema.get("properties", {})
