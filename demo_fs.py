"""
demo_fs.py — Autonomous filesystem analysis with dynamic task allocation.

Agents autonomously:
  1. Discover directory structure via shell commands (find/ls)
  2. Read source files with read_file
  3. Allocate subtasks to child agents via the `task` tool
  4. Write the final report to disk with write_file (no manual save)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True), override=False)

from deepagents.backends import LocalShellBackend
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent_tree.tree_agent import create_tree_agent

MODEL = os.environ.get("AGENT_TREE_MODEL", "openai:deepseek-v4-pro")
MAX_DEPTH = int(os.environ.get("AGENT_TREE_MAX_DEPTH", "3"))

# Default: analyse this project itself. Pass a path as CLI arg to override.
TARGET_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
OUTPUT_FILE = TARGET_DIR / "report.md"

# System prompt that makes agents aware of their filesystem tools
_FS_SYSTEM_PROMPT = """\
You are a filesystem-aware tree-structured analysis agent.

You have three categories of tools:
  • Shell execution — `execute(cmd)`: run any shell command (find, ls, grep, cat, wc, etc.)
  • File I/O — `read_file(path)`: read a file; `write_file(path, content)`: write a file
  • Delegation — `task(description)`: spawn an independent sub-agent for a focused subtask

Workflow for analysing a codebase:
  1. Explore structure first: `execute("find . -not -path '*/.venv/*' -not -path '*/__pycache__/*' | sort")`
  2. Identify logical module groups from the file list
  3. Delegate each group to a sub-agent via `task(...)` — sub-agents run in parallel
  4. Each sub-agent should read its assigned files and return a detailed technical summary
  5. Synthesise all sub-agent results into a comprehensive final report
  6. Write the report to the output path using `write_file`

Be autonomous: do not ask for clarification. Explore, delegate, synthesise, and write.
"""


def _print_trace(messages: list) -> None:
    print("\n── Agent tool-call trace ──")
    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage):
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    name = tc.get("name", "?")
                    args = tc.get("args", {})
                    arg_preview = next(iter(args.values()), args) if args else ""
                    print(f"  [{i:02d}] → {name}({str(arg_preview)[:100]})")
            elif msg.content:
                preview = str(msg.content)
                print(f"  [{i:02d}] AI: {preview[:120]}{'…' if len(preview) > 120 else ''}")
        elif isinstance(msg, ToolMessage):
            preview = str(msg.content)[:80].replace("\n", " ")
            print(f"  [{i:02d}] ← {msg.name}: {preview}…")


async def main() -> None:
    print(f"model      = {MODEL}")
    print(f"max_depth  = {MAX_DEPTH}")
    print(f"target_dir = {TARGET_DIR}")
    print(f"output     = {OUTPUT_FILE}")
    print(f"mode       = FREE — agent autonomously explores and writes output")
    print()

    backend = LocalShellBackend(root_dir=str(TARGET_DIR), virtual_mode=True)

    agent = create_tree_agent(
        MODEL,
        backend=backend,
        max_depth=MAX_DEPTH,
        system_prompt=_FS_SYSTEM_PROMPT,
    )

    task = (
        f"Analyse the Python project in the current working directory.\n"
        f"Write the final architecture report to `/report.md`.\n"
        f"Be autonomous — explore the directory, delegate subtasks, synthesise, and write."
    )

    print("Running… (agent will autonomously explore and write report.md)")
    print("-" * 60)

    state = await agent.ainvoke({"messages": [HumanMessage(content=task)]})
    messages = state.get("messages", [])

    _print_trace(messages)

    # Check if agent wrote the file itself
    if OUTPUT_FILE.exists():
        print(f"\n✓ Agent wrote {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size} bytes)")
    else:
        # Fallback: extract from messages and save manually
        print(f"\n⚠ Agent did not call write_file — saving final message manually")
        result = "(no result)"
        for msg in reversed(messages):
            content = getattr(msg, "content", None)
            tool_calls = getattr(msg, "tool_calls", None)
            if content and isinstance(content, str) and not tool_calls:
                result = content
                break
        OUTPUT_FILE.write_text(result, encoding="utf-8")
        print(f"  saved → {OUTPUT_FILE}")

    print(f"\n{'=' * 70}")
    print(f"Report saved to: {OUTPUT_FILE}")
    print(f"{'=' * 70}")
    print(OUTPUT_FILE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    asyncio.run(main())
