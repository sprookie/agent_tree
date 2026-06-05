#!/usr/bin/env python3
"""Demo script for Agent Tree."""

import argparse
import asyncio
import os
from pathlib import Path
import sys


def _load_env() -> None:
    for path in [
        Path(__file__).resolve().parent / ".env",
        Path.cwd() / ".env",
    ]:
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    key = key.removeprefix("export ").strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val


DEMO_TREE = """@tree
Analyze the concept of "agent tree" architecture for AI coding agents
  - Research what problem agent trees solve
    - Identify limitations of flat subagent architectures
    - Understand how hierarchical delegation reduces context pressure
    - Find real-world examples where trees outperform flat structures
  - Compare with existing solutions
    - How does dcode handle subagent delegation
    - How does CodeWhale handle parallel subagent execution
    - What are the key differences between tree and flat approaches
  - Synthesize findings into key insights
    - What are the most important design principles
    - What common pitfalls to avoid
    - What use cases benefit most from tree architecture
"""


def main() -> None:
    _load_env()
    parser = argparse.ArgumentParser(description="Agent Tree Demo")
    parser.add_argument("--tui", action="store_true", help="Launch TUI mode")
    parser.add_argument("--headless", action="store_true", help="Run headless")
    args = parser.parse_args()

    if args.tui:
        from agent_tree.cli import _run_tui
        _run_tui(argparse.Namespace(model="deepseek-reasoner", max_depth=3))
        return
    if args.headless:
        _run_headless_demo()
        return

    print("Agent Tree Demo")
    print("===============")
    print()
    print("Run modes:")
    print("  python demo.py --tui      Launch Textual TUI")
    print("  python demo.py --headless  Run demo task headless")
    print()


def _run_headless_demo() -> None:
    import rich.console
    from agent_tree.tree_parser import TreeParser
    from agent_tree.tree_executor import TreeExecutor
    from deepagents.backends.state import StateBackend
    from langchain_openai import ChatOpenAI

    console = rich.console.Console()

    parser = TreeParser()
    tree = parser.parse(DEMO_TREE)
    if not tree:
        console.print("[red]Failed to parse demo tree[/red]")
        return

    console.print("[bold]Parsed tree:[/bold]")
    console.print(f"  Root: {tree.description}")
    for child in tree.children:
        console.print(f"    L1: {child.description} ({len(child.children)} children)")

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        console.print("[red]DEEPSEEK_API_KEY not set. Source .env or set it and retry.[/red]")
        sys.exit(1)

    model = ChatOpenAI(model="deepseek-reasoner", api_key=api_key, base_url="https://api.deepseek.com/v1", temperature=0)
    backend = StateBackend()
    executor = TreeExecutor(model=model, tools=[], backend=backend, max_depth=3)

    async def run() -> None:
        with console.status("[bold green]Executing demo tree..."):
            result = await executor.execute(tree)
        console.print("\n[bold]Demo Result:[/bold]")
        console.print(result)

    asyncio.run(run())


if __name__ == "__main__":
    main()
