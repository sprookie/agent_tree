"""Indentation-based tree syntax parser.

Parses @tree blocks where indentation defines parent-child relationships.

Example:
    @tree
    analyze linux kernel
      - analyze CFS scheduler
        - data structures
        - entry functions
      - analyze RT scheduler
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class TreeNode:
    """A node in the task tree."""

    description: str
    """Task description for this node."""

    children: list[TreeNode] = field(default_factory=list)
    """Child nodes (sub-tasks)."""

    depth: int = 0
    """Depth in the tree (0 = root)."""

    parent: TreeNode | None = field(default=None, repr=False)
    """Parent node, None for root."""

    def __repr__(self) -> str:
        return (
            f"TreeNode(description={self.description!r}, "
            f"depth={self.depth}, "
            f"children={len(self.children)})"
        )


class TreeParser:
    """Parse indented @tree blocks into TreeNode structures."""

    def parse(self, text: str) -> TreeNode | None:
        """Parse text containing a @tree block.

        Lines after `@tree` define the tree structure.
        Indentation (2/4 spaces or tab) determines parent-child relationships.
        Lines starting with `- `, `* ` have the prefix stripped.
        Empty lines and `#` comment lines are ignored.

        Args:
            text: Raw text containing `@tree` marker and indented structure.

        Returns:
            Root TreeNode if a @tree block was found, None otherwise.
        """
        lines = text.split("\n")
        tree_lines = self._extract_tree_lines(lines)
        if not tree_lines:
            return None
        return self._build_tree(tree_lines)

    def parse_file(self, path: Path) -> TreeNode | None:
        """Parse a file containing a @tree block.

        Args:
            path: Path to the file.

        Returns:
            Root TreeNode if found, None otherwise.
        """
        return self.parse(path.read_text(encoding="utf-8"))

    def _extract_tree_lines(self, lines: list[str]) -> list[str]:
        """Extract @tree block content, stripping the marker line."""
        in_tree = False
        tree_lines: list[str] = []
        for line in lines:
            if line.strip() == "@tree":
                in_tree = True
                continue
            if not in_tree:
                continue
            stripped = line.rstrip()
            if stripped == "" or stripped.lstrip().startswith("#"):
                continue
            tree_lines.append(line)
        return tree_lines

    def _build_tree(self, lines: list[str]) -> TreeNode:
        """Build TreeNode tree from indented lines using a stack."""
        indent_unit = self._detect_indent_unit(lines)
        root_line = lines[0].strip()
        root_desc = self._clean_line(root_line)
        root = TreeNode(description=root_desc, depth=0)
        stack: list[tuple[int, TreeNode]] = [(0, root)]

        for line in lines[1:]:
            stripped = line.lstrip()
            leading = len(line) - len(line.lstrip())
            level = leading // indent_unit if indent_unit > 0 else 0

            desc = self._clean_line(stripped)

            while stack and stack[-1][0] >= level:
                stack.pop()

            if not stack:
                continue

            _parent_level, parent = stack[-1]
            child = TreeNode(
                description=desc,
                depth=parent.depth + 1,
                parent=parent,
            )
            parent.children.append(child)
            stack.append((level, child))

        return root

    @staticmethod
    def _detect_indent_unit(lines: list[str]) -> int:
        """Detect the indent unit from the first indented line."""
        for line in lines[1:]:
            leading = len(line) - len(line.lstrip())
            if leading > 0:
                if line[0] == "\t":
                    return 1
                return leading
        return 2

    @staticmethod
    def _clean_line(line: str) -> str:
        """Strip bullet markers and whitespace from a line."""
        text = line.strip()
        if text.startswith("- ") or text.startswith("* "):
            text = text[2:].strip()
        return text
