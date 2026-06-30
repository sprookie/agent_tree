"""
demo_fs.py — Real filesystem analysis + dynamic task allocation.

Differences from demo.py:
  - Backend: LocalShellBackend (agents get find/cat/grep/shell access)
  - Mode: FREE (no @tree) — root agent dynamically allocates subtasks
    via the `task` tool, proving parent → child delegation works

The task points at this project's own source code so we can verify
agents actually read real files rather than hallucinating from training data.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True), override=False)

from deepagents.backends import LocalShellBackend
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent_tree.tree_agent import create_tree_agent

MODEL = os.environ.get("AGENT_TREE_MODEL", "openai:deepseek-v4-pro")
MAX_DEPTH = int(os.environ.get("AGENT_TREE_MAX_DEPTH", "3"))

# Point agents at this project's source code
PROJECT_DIR = Path(__file__).parent

TASK = """\
Analyse the agent_tree Python project in the current working directory.

Start by running: find . -name "*.py" -not -path "*/__pycache__/*" | sort
Then read the key source files to understand the codebase.

Decompose into subtasks using the `task` tool — assign each major module
group to a separate sub-agent:
  - Parser + data model (tree_node.py, tree_parser.py)
  - Execution engine (tree_executor.py, tree_agent.py)
  - TUI layer (tui/ directory)

Each sub-agent should read the actual source files and produce a
technical summary. After all sub-agents report back, synthesise a
comprehensive architecture report.
"""


def _print_trace(messages: list) -> None:
    """Print a compact trace of tool calls to show dynamic task allocation."""
    print("\n── Agent message trace ──")
    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage):
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    name = tc.get("name", "?")
                    args = tc.get("args", {})
                    # Show first arg value as the "what" being called
                    arg_preview = next(iter(args.values()), args) if args else ""
                    print(f"  [{i:02d}] → {name}({str(arg_preview)[:100]})")
            elif msg.content:
                preview = str(msg.content)
                if len(preview) > 120:
                    preview = preview[:120] + "…"
                print(f"  [{i:02d}] AI: {preview}")
        elif isinstance(msg, ToolMessage):
            content_preview = str(msg.content)[:80].replace("\n", " ")
            print(f"  [{i:02d}] ← {msg.name}: {content_preview}…")


async def main() -> None:
    print(f"model      = {MODEL}")
    print(f"max_depth  = {MAX_DEPTH}")
    print(f"root_dir   = {PROJECT_DIR}")
    print(f"mode       = FREE (root agent allocates subtasks via `task` tool)")
    print()

    # virtual_mode=True: /src/foo.py → PROJECT_DIR/src/foo.py (cleaner for read_file)
    backend = LocalShellBackend(root_dir=str(PROJECT_DIR), virtual_mode=True)
    agent = create_tree_agent(MODEL, backend=backend, max_depth=MAX_DEPTH)

    print("Running… (this makes real LLM + shell calls)")
    print("-" * 60)

    state = await agent.ainvoke({"messages": [HumanMessage(content=TASK)]})
    messages = state.get("messages", [])

    _print_trace(messages)

    # Extract final answer (last AI message without tool calls)
    result = "(no result)"
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        tool_calls = getattr(msg, "tool_calls", None)
        if content and isinstance(content, str) and not tool_calls:
            result = content
            break

    print()
    print("=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
