from __future__ import annotations

import argparse
import asyncio
import sys

from langchain_core.messages import HumanMessage

from .tree_agent import create_tree_agent
from .tree_executor import TreeExecutor
from .tree_parser import TreeParser
from .tui.app import TreeApp


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent-tree",
        description="Multi-level tree-shaped sub-agent system",
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="Task string (omit to open TUI)",
    )
    parser.add_argument(
        "--model",
        default="anthropic:claude-sonnet-4-6",
        help="Model identifier (default: anthropic:claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=3,
        dest="max_depth",
        help="Maximum recursion depth (default: 3)",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Force TUI mode even if task is provided",
    )
    args = parser.parse_args()

    if args.task and not args.tui:
        asyncio.run(_run_cli(args.task, args.model, args.max_depth))
    else:
        app = TreeApp(model=args.model, max_depth=args.max_depth)
        app.run()


async def _run_cli(task: str, model: str, max_depth: int) -> None:
    print(f"[agent-tree] model={model}  max_depth={max_depth}")
    print(f"[agent-tree] task: {task[:80]}")
    print()

    parser = TreeParser()
    tree = parser.parse(task)

    def on_event(evt):
        path_str = ".".join(str(i) for i in evt.node_path) or "root"
        if evt.status == "running":
            print(f"  → [{path_str}] {evt.description[:60]}")
        elif evt.status == "done":
            print(f"  ✓ [{path_str}] done ({evt.elapsed:.1f}s)")
        elif evt.status == "error":
            print(f"  ✗ [{path_str}] error: {evt.error}")

    import asyncio
    queue: asyncio.Queue = asyncio.Queue()

    async def drain():
        while True:
            try:
                evt = queue.get_nowait()
                on_event(evt)
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.05)

    executor = TreeExecutor(model, max_depth=max_depth, event_queue=queue)
    drain_task = asyncio.create_task(drain())

    try:
        result = await executor.execute(tree)
    finally:
        drain_task.cancel()
        # Drain remaining events
        while not queue.empty():
            on_event(queue.get_nowait())

    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)
    print(result)
