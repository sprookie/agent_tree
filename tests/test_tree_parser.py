import pytest

from agent_tree import TreeNode, TreeParser


@pytest.fixture
def parser():
    return TreeParser()


def test_parse_no_tree_marker(parser):
    tree = parser.parse("Just a plain task")
    assert tree.description == "Just a plain task"
    assert tree.children == []
    assert tree.node_path == ()


def test_parse_tree_flat(parser):
    text = """@tree
root task
  - child one
  - child two
"""
    tree = parser.parse(text)
    assert tree.description == "root task"
    assert len(tree.children) == 2
    assert tree.children[0].description == "child one"
    assert tree.children[1].description == "child two"


def test_parse_tree_nested(parser):
    text = """@tree
root
  - level 1a
      - level 2a
      - level 2b
  - level 1b
"""
    tree = parser.parse(text)
    assert tree.description == "root"
    assert len(tree.children) == 2

    l1a = tree.children[0]
    assert l1a.description == "level 1a"
    assert len(l1a.children) == 2
    assert l1a.children[0].description == "level 2a"
    assert l1a.children[1].description == "level 2b"

    l1b = tree.children[1]
    assert l1b.description == "level 1b"
    assert l1b.children == []


def test_parse_node_paths(parser):
    text = """@tree
root
  - a
      - a1
  - b
"""
    tree = parser.parse(text)
    assert tree.node_path == ()
    assert tree.children[0].node_path == (0,)
    assert tree.children[0].children[0].node_path == (0, 0)
    assert tree.children[1].node_path == (1,)


def test_parse_ignores_comments_and_blanks(parser):
    text = """@tree
root task

# this is a comment
  - child one

  - child two
"""
    tree = parser.parse(text)
    assert len(tree.children) == 2


def test_parse_star_marker(parser):
    text = """@tree
root
  * item a
  * item b
"""
    tree = parser.parse(text)
    assert tree.children[0].description == "item a"


def test_is_leaf(parser):
    text = """@tree
root
  - child
"""
    tree = parser.parse(text)
    assert not tree.is_leaf()
    assert tree.children[0].is_leaf()


def test_iter_leaves(parser):
    text = """@tree
root
  - a
      - a1
      - a2
  - b
"""
    tree = parser.parse(text)
    leaves = tree.iter_leaves()
    assert len(leaves) == 3
    descs = {n.description for n in leaves}
    assert descs == {"a1", "a2", "b"}


def test_depth_assigned(parser):
    text = """@tree
root
  - child
      - grandchild
"""
    tree = parser.parse(text)
    assert tree.depth == 0
    assert tree.children[0].depth == 1
    assert tree.children[0].children[0].depth == 2
