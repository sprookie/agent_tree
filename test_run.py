#!/usr/bin/env python3
"""Run the scheduler analysis test with real DeepSeek API calls."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "agent_tree"))

from agent_tree.tree_parser import TreeParser
from agent_tree.tree_executor import TreeExecutor
from deepagents.backends.filesystem import FilesystemBackend
from langchain_openai import ChatOpenAI
import rich.console


def load_env():
    for p in [Path(__file__).resolve().parent / "agent_tree" / ".env", Path.cwd() / ".env"]:
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k = k.removeprefix("export ").strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v


async def main():
    load_env()
    console = rich.console.Console()

    task_file = Path(__file__).resolve().parent / "test_scheduler.txt"
    if not task_file.exists():
        console.print(f"[red]Task file not found: {task_file}[/red]")
        return

    tree = TreeParser().parse_file(task_file)
    if not tree:
        console.print("[red]No @tree block found[/red]")
        return

    console.print("[bold]Parsed tree:[/bold]")
    console.print(f"  Root: {tree.description}")
    for child in tree.children:
        console.print(f"    L1: {child.description} ({len(child.children)} children)")

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        console.print("[red]DEEPSEEK_API_KEY not set[/red]")
        return

    model = ChatOpenAI(
        model="deepseek-reasoner",
        api_key=api_key,
        base_url="https://api.deepseek.com/v1",
        temperature=0,
    )

    backend = FilesystemBackend(root_dir="/home/user/agent_tree/reference/linux")
    executor = TreeExecutor(model=model, tools=[], backend=backend, max_depth=3)

    started = {}
    completed = {}

    def on_start(node, result, error):
        started[node.description] = True
        console.print(f"  [yellow]▶[/yellow] L{node.depth}: {node.description[:60]}...")

    def on_complete(node, result, error):
        completed[node.description] = True
        icon = "[red]✗[/red]" if error else "[green]✓[/green]"
        console.print(f"  {icon} L{node.depth}: {node.description[:60]}...")

    executor.on_node_start(on_start)
    executor.on_node_complete(on_complete)

    console.print("\n[bold green]Executing tree...[/bold green]\n")
    t0 = __import__("time").monotonic()
    result = await executor.execute(tree)
    elapsed = __import__("time").monotonic() - t0

    console.print(f"\n[bold]Execution time:[/bold] {elapsed:.1f}s")
    console.print(f"[bold]Nodes completed:[/bold] {len(completed)}")
    console.print(f"\n[bold]=== Final Report ===[/bold]\n")
    console.print(result)


if __name__ == "__main__":
    asyncio.run(main())
