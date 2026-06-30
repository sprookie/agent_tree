from __future__ import annotations

import asyncio

from ..tree_executor import NodeEvent
from .widgets.tree_view import TreeView


class TreeUIAdapter:
    """Consumes NodeEvent from a queue and updates TreeView widgets."""

    def __init__(self, tree_view: TreeView) -> None:
        self.queue: asyncio.Queue[NodeEvent] = asyncio.Queue()
        self._tree_view = tree_view
        self._running = False

    async def run(self) -> None:
        self._running = True
        while self._running:
            try:
                event = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                self._apply(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    def stop(self) -> None:
        self._running = False

    def _apply(self, event: NodeEvent) -> None:
        self._tree_view.upsert_node(
            node_path=event.node_path,
            description=event.description,
            status=event.status,
            elapsed=event.elapsed,
            error=event.error,
        )
