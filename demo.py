"""Demo script: run a 3-level tree agent on a sample task."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True), override=False)

from agent_tree import TreeExecutor, TreeParser
from agent_tree.tree_executor import NodeEvent


SAMPLE_TASK = """@tree
Analyse the Python asyncio event loop implementation
  - Analyse the core event loop
      - Event loop base class design
      - Task scheduling mechanism
  - Analyse I/O handling
      - Selector event loop
      - Transport and protocol abstractions
  - Analyse coroutine integration
      - How coroutines are scheduled
      - Cancellation mechanism
"""

MODEL = os.environ.get("AGENT_TREE_MODEL", "openai:deepseek-v4-pro")
MAX_DEPTH = int(os.environ.get("AGENT_TREE_MAX_DEPTH", "3"))


async def main():
    print(f"model: {MODEL}  max_depth: {MAX_DEPTH}")
    print()

    parser = TreeParser()
    tree = parser.parse(SAMPLE_TASK)

    queue: asyncio.Queue[NodeEvent] = asyncio.Queue()

    async def log_events():
        while True:
            event: NodeEvent = await queue.get()
            path = ".".join(str(i) for i in event.node_path) or "root"
            icon = {"running": "◷", "done": "✓", "error": "✗", "pending": "○"}[event.status]
            elapsed = f" ({event.elapsed:.1f}s)" if event.elapsed else ""
            print(f"  {icon} [{path}] {event.description[:60]}{elapsed}")

    log_task = asyncio.create_task(log_events())

    executor = TreeExecutor(MODEL, max_depth=MAX_DEPTH, event_queue=queue)
    result = await executor.execute(tree)

    log_task.cancel()
    # flush remaining events
    while not queue.empty():
        evt = queue.get_nowait()
        path = ".".join(str(i) for i in evt.node_path) or "root"
        print(f"  {evt.status} [{path}] {evt.description[:60]}")

    print()
    print("=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
