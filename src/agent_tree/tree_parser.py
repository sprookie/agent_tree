from __future__ import annotations

import re
from pathlib import Path

from .tree_node import TreeNode


class TreeParser:
    """Parse @tree indented syntax into a TreeNode hierarchy."""

    _MARKER_RE = re.compile(r"^[-*]\s+")

    def parse(self, text: str) -> TreeNode:
        lines = text.splitlines()
        start = self._find_tree_start(lines)
        if start is None:
            # Treat entire text as a flat single-node task
            return TreeNode(description=text.strip(), depth=0, node_path=())
        return self._parse_lines(lines[start:])

    def parse_file(self, path: Path) -> TreeNode:
        return self.parse(path.read_text())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_tree_start(self, lines: list[str]) -> int | None:
        for i, line in enumerate(lines):
            if line.strip() == "@tree":
                return i + 1
        return None

    def _strip_marker(self, text: str) -> str:
        return self._MARKER_RE.sub("", text)

    def _detect_indent(self, lines: list[str]) -> int:
        """Return the smallest non-zero indent width found in the lines."""
        for line in lines:
            if not line.strip() or line.strip().startswith("#"):
                continue
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if indent > 0:
                return indent
        return 2  # default

    def _parse_lines(self, lines: list[str]) -> TreeNode:
        # Filter blank lines and comments
        content = [
            line for line in lines if line.strip() and not line.strip().startswith("#")
        ]
        if not content:
            return TreeNode(description="(empty tree)", depth=0, node_path=())

        indent_unit = self._detect_indent(content)

        # Root is the first non-indented line
        root_text = self._strip_marker(content[0].lstrip()).strip()
        root = TreeNode(description=root_text, depth=0, node_path=())

        # Stack holds (node, indent_level)
        stack: list[tuple[TreeNode, int]] = [(root, 0)]

        for line in content[1:]:
            raw_indent = len(line) - len(line.lstrip())
            depth = raw_indent // indent_unit
            description = self._strip_marker(line.lstrip()).strip()
            if not description:
                continue

            # Pop stack until we find the parent
            while len(stack) > 1 and stack[-1][1] >= depth:
                stack.pop()

            parent_node, _ = stack[-1]
            child_idx = len(parent_node.children)
            node = TreeNode(
                description=description,
                depth=parent_node.depth + 1,
                node_path=parent_node.node_path + (child_idx,),
            )
            parent_node.children.append(node)
            stack.append((node, depth))

        return root
