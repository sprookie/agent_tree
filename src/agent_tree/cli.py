from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Search parent directories for .env (works regardless of install location)
load_dotenv(find_dotenv(usecwd=True), override=False)

from .tree_executor import NodeEvent, TreeExecutor
from .tree_parser import TreeParser
from .tui.app import TreeApp


def main() -> None:
    _default_model = os.environ.get("AGENT_TREE_MODEL", "openai:deepseek-v4-pro")
    _default_depth = int(os.environ.get("AGENT_TREE_MAX_DEPTH", "3"))

    parser = argparse.ArgumentParser(
        prog="agent-tree",
        description="Multi-level tree-shaped sub-agent system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  agent-tree                                  # open TUI
  agent-tree "analyse Linux scheduler"        # CLI one-shot
  agent-tree --max-depth 2 "summarise XYZ"   # limit depth
  agent-tree --tui "any task"                 # force TUI
""",
    )
    parser.add_argument("task", nargs="?", help="Task (omit to open TUI)")
    parser.add_argument(
        "--model",
        default=_default_model,
        help=f"Model identifier (default: {_default_model})",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=_default_depth,
        dest="max_depth",
        help=f"Maximum recursion depth (default: {_default_depth})",
    )
    parser.add_argument("--tui", action="store_true", help="Force TUI mode")
    args = parser.parse_args()

    if args.task and not args.tui:
        asyncio.run(_run_cli(args.task, args.model, args.max_depth))
    else:
        TreeApp(model=args.model, max_depth=args.max_depth).run()


async def _run_cli(task: str, model: str, max_depth: int) -> None:
    print(f"[agent-tree] model={model}  max_depth={max_depth}")
    print(f"[agent-tree] task: {task[:100]}")
    print()

    tree = TreeParser().parse(task)

    queue: asyncio.Queue[NodeEvent] = asyncio.Queue()
    executor = TreeExecutor(model, max_depth=max_depth, event_queue=queue)

    # Drain events concurrently while executor runs
    async def _drain() -> None:
        while True:
            event: NodeEvent = await queue.get()
            _print_event(event)

    drain_task = asyncio.create_task(_drain())
    try:
        result = await executor.execute(tree)
    finally:
        # Let drain flush remaining events before cancelling
        await asyncio.sleep(0.05)
        drain_task.cancel()
        try:
            await drain_task
        except asyncio.CancelledError:
            pass
        # Flush any stragglers
        while not queue.empty():
            _print_event(queue.get_nowait())

    print()
    print("═" * 65)
    print("  RESULT")
    print("═" * 65)
    print(result)


def _print_event(evt: NodeEvent) -> None:
    path = ".".join(str(i) for i in evt.node_path) or "root"
    icon = {"running": "◷", "done": "✓", "error": "✗", "pending": "○"}[evt.status]
    desc = evt.description[:60]
    timing = f" ({evt.elapsed:.1f}s)" if evt.elapsed else ""
    err = f"  ← {evt.error}" if evt.error else ""
    print(f"  {icon} [{path}] {desc}{timing}{err}")
