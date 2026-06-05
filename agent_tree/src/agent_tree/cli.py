"""CLI entry point for agent-tree."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys


def _load_env() -> None:
    """Load .env from project root or current directory."""
    for path in [
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path.cwd() / ".env",
        Path.cwd() / "agent_tree" / ".env",
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


def main() -> None:
    _load_env()
    """Entry point for the agent-tree CLI."""
    parser = argparse.ArgumentParser(
        prog="agent-tree",
        description="Multi-level tree-based coding agent harness",
    )
    parser.add_argument("--model", default="deepseek-reasoner", help="Model to use")
    parser.add_argument("--max-depth", type=int, default=3, help="Maximum tree depth")
    parser.add_argument("--api-key", help="DeepSeek API key (or set DEEPSEEK_API_KEY env var)")
    parser.add_argument("--api-base", default="https://api.deepseek.com/v1", help="API base URL")
    parser.add_argument("--file", "-f", help="Read @tree task from file")
    parser.add_argument("--no-tui", action="store_true", help="Run without TUI (headless)")

    args = parser.parse_args()

    if args.api_key:
        os.environ["DEEPSEEK_API_KEY"] = args.api_key

    if args.file or args.no_tui:
        _run_headless(args)
    else:
        _run_tui(args)


def _run_tui(args: argparse.Namespace) -> None:
    from agent_tree.tui.app import TreeApp
    app = TreeApp(model=args.model, max_depth=args.max_depth)
    app.run()


def _run_headless(args: argparse.Namespace) -> None:
    from pathlib import Path
    import rich.console
    from agent_tree.tree_parser import TreeParser
    from agent_tree.tree_executor import TreeExecutor
    from deepagents.backends.state import StateBackend
    from langchain_openai import ChatOpenAI

    console = rich.console.Console()

    if args.file:
        tree = TreeParser().parse_file(Path(args.file))
    else:
        console.print("[red]Use --file to specify a task file, or run without --no-tui.[/red]")
        sys.exit(1)

    if tree is None:
        console.print("[red]No @tree block found in file.[/red]")
        sys.exit(1)

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    model = ChatOpenAI(model=args.model, api_key=api_key, base_url=args.api_base, temperature=0)
    backend = StateBackend()
    executor = TreeExecutor(model=model, tools=[], backend=backend, max_depth=args.max_depth)

    async def run() -> None:
        with console.status("[bold green]Executing tree..."):
            result = await executor.execute(tree)
        console.print("\n[bold]Result:[/bold]")
        console.print(result)

    asyncio.run(run())


if __name__ == "__main__":
    main()
