from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TreeNode:
    description: str
    children: list[TreeNode] = field(default_factory=list)
    depth: int = 0
    # Full index path from root, e.g. () for root, (0,) for first child
    node_path: tuple[int, ...] = field(default_factory=tuple)

    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def iter_leaves(self) -> list[TreeNode]:
        if self.is_leaf():
            return [self]
        result = []
        for child in self.children:
            result.extend(child.iter_leaves())
        return result

    def iter_all(self) -> list[TreeNode]:
        result = [self]
        for child in self.children:
            result.extend(child.iter_all())
        return result
