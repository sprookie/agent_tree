import pytest
from agent_tree.tree_parser import TreeParser, TreeNode


def test_parse_single_line_root():
    parser = TreeParser()
    tree = parser.parse("@tree\nanalyze linux scheduler")
    assert tree is not None
    assert tree.description == "analyze linux scheduler"
    assert tree.children == []
    assert tree.depth == 0


def test_parse_one_level_children():
    parser = TreeParser()
    tree = parser.parse("""@tree
analyze linux scheduler
  - analyze CFS logic
  - analyze RT scheduler
  - analyze deadline""")
    assert tree is not None
    assert tree.description == "analyze linux scheduler"
    assert len(tree.children) == 3
    assert tree.children[0].description == "analyze CFS logic"
    assert tree.children[0].depth == 1
    assert tree.children[1].description == "analyze RT scheduler"
    assert tree.children[2].description == "analyze deadline"


def test_parse_two_levels():
    parser = TreeParser()
    tree = parser.parse("""@tree
root task
  - child A
    - grandchild A1
    - grandchild A2
  - child B
    - grandchild B1""")
    assert tree is not None
    assert tree.description == "root task"
    assert len(tree.children) == 2
    child_a = tree.children[0]
    assert child_a.description == "child A"
    assert child_a.depth == 1
    assert len(child_a.children) == 2
    assert child_a.children[0].description == "grandchild A1"
    assert child_a.children[0].depth == 2
    child_b = tree.children[1]
    assert len(child_b.children) == 1
    assert child_b.children[0].description == "grandchild B1"


def test_parse_strips_bullet_markers():
    parser = TreeParser()
    tree = parser.parse("""@tree
root
  * with star
  - with dash""")
    assert tree is not None
    assert tree.children[0].description == "with star"
    assert tree.children[1].description == "with dash"


def test_parse_ignores_empty_lines_and_comments():
    parser = TreeParser()
    tree = parser.parse("""@tree
root task

  # this is a comment
  - child task

  - another child""")
    assert tree is not None
    assert len(tree.children) == 2
    assert tree.children[0].description == "child task"
    assert tree.children[1].description == "another child"


def test_parse_without_tree_marker_returns_none():
    parser = TreeParser()
    tree = parser.parse("just some text\n  - not a tree")
    assert tree is None


def test_parse_with_2_space_indent():
    parser = TreeParser()
    tree = parser.parse("@tree\nroot\n  child1\n    grandchild\n  child2")
    assert tree is not None
    assert len(tree.children) == 2
    assert len(tree.children[0].children) == 1


def test_parse_with_4_space_indent():
    parser = TreeParser()
    tree = parser.parse("@tree\nroot\n    child1\n        grandchild\n    child2")
    assert tree is not None
    assert len(tree.children) == 2
    assert len(tree.children[0].children) == 1


def test_parse_with_tab_indent():
    parser = TreeParser()
    tree = parser.parse("@tree\nroot\n\tchild1\n\t\tgrandchild\n\tchild2")
    assert tree is not None
    assert len(tree.children) == 2
    assert len(tree.children[0].children) == 1


def test_parse_hierarchical_deep_task():
    """Verify 3-level tree with multiple branches."""
    parser = TreeParser()
    tree = parser.parse("""@tree
analyze linux kernel scheduler
  - CFS scheduler analysis
    - sched_entity data structures
    - load_balance logic
    - task migration
  - RT scheduler analysis
    - FIFO implementation
    - RR implementation
  - Deadline scheduler
    - EDF algorithm
    - CBS bandwidth control""")
    assert tree is not None
    assert tree.description == "analyze linux kernel scheduler"
    assert len(tree.children) == 3
    assert len(tree.children[0].children) == 3
    assert len(tree.children[1].children) == 2
    assert len(tree.children[2].children) == 2


def test_node_repr():
    node = TreeNode(description="test", depth=1)
    rep = repr(node)
    assert "test" in rep
    assert "depth=1" in rep
    assert "children=0" in rep
