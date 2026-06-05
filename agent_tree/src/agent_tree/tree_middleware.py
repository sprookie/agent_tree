"""TreeMiddleware — recursive depth-controlled subagent spawner.

Each agent node at depth < max_depth gets a `task` tool that can spawn
child agents at depth+1. Child agents also get TreeMiddleware recursive.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command
from pydantic import BaseModel, Field

from deepagents.backends.protocol import BackendProtocol

if TYPE_CHECKING:
    from langchain.agents.middleware.types import ModelRequest, ModelResponse
    from langchain.tools import ToolRuntime


class TaskToolSchema(BaseModel):
    """Input schema for the tree task tool."""
    description: str = Field(description="A detailed description of the task for the sub-agent to perform.")
    subagent_type: str = Field(default="general-purpose", description="The type of subagent to use.")


TREE_TASK_TOOL_DESC = """Launch a sub-agent to handle isolated tasks at the next tree level.
Each sub-agent has its own context. Results are returned as a single summary.
Usage: Launch multiple in parallel when tasks are independent."""

TREE_SYSTEM_PROMPT = """## `task` (tree sub-agent spawner)

You can spawn sub-agents to handle isolated subtasks at the next tree level.
Use them to break complex tasks into parallel subtasks and isolate context-heavy work.
Each sub-agent returns a single summary when done."""


class TreeMiddleware(AgentMiddleware[Any, Any, Any]):
    """Adds recursive tree-spawning capability. At depth >= max_depth, no task tool."""

    def __init__(
        self,
        *,
        depth: int,
        max_depth: int,
        model: str | BaseChatModel,
        tools: list[BaseTool],
        backend: BackendProtocol,
        subagent_prompt: str | None = None,
    ) -> None:
        super().__init__()
        self._depth = depth
        self._max_depth = max_depth
        self._model = model
        self._tools = list(tools)
        self._backend = backend
        self._subagent_prompt = subagent_prompt or TREE_SYSTEM_PROMPT

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def max_depth(self) -> int:
        return self._max_depth

    @property
    def tools(self) -> list[BaseTool]:
        if self._depth >= self._max_depth:
            return []
        return [self._build_task_tool()]

    @property
    def system_prompt(self) -> str | None:
        if self._depth >= self._max_depth:
            return None
        return self._subagent_prompt

    def _build_task_tool(self) -> BaseTool:
        """Build a task tool that spawns a child agent at depth+1."""
        from deepagents import create_deep_agent

        next_depth = self._depth + 1

        def _task(
            description: str,
            runtime: "ToolRuntime",
            subagent_type: str = "general-purpose",
        ) -> str | Command:
            child_graph = create_deep_agent(
                model=self._model,
                tools=self._tools,
                middleware=[
                    TreeMiddleware(
                        depth=next_depth,
                        max_depth=self._max_depth,
                        model=self._model,
                        tools=self._tools,
                        backend=self._backend,
                    ),
                ],
                backend=self._backend,
                name=f"tree-L{next_depth}-{subagent_type}",
            )
            child_state = {"messages": [HumanMessage(content=description)]}
            config: RunnableConfig = {"configurable": {"ls_agent_type": "subagent"}}
            result = child_graph.invoke(child_state, config)
            content = ""
            for msg in reversed(result["messages"]):
                if isinstance(msg, AIMessage) and msg.text and msg.text.strip():
                    content = msg.text
                    break
            if not content:
                content = "(sub-agent returned no result)"
            return Command(update={
                "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id)]
            })

        async def _atask(
            description: str,
            runtime: "ToolRuntime",
            subagent_type: str = "general-purpose",
        ) -> str | Command:
            from deepagents import create_deep_agent
            child_graph = create_deep_agent(
                model=self._model,
                tools=self._tools,
                middleware=[
                    TreeMiddleware(depth=next_depth, max_depth=self._max_depth, model=self._model, tools=self._tools, backend=self._backend),
                ],
                backend=self._backend,
                name=f"tree-L{next_depth}-{subagent_type}",
            )
            child_state = {"messages": [HumanMessage(content=description)]}
            config: RunnableConfig = {"configurable": {"ls_agent_type": "subagent"}}
            result = await child_graph.ainvoke(child_state, config)
            content = ""
            for msg in reversed(result["messages"]):
                if isinstance(msg, AIMessage) and msg.text and msg.text.strip():
                    content = msg.text
                    break
            if not content:
                content = "(sub-agent returned no result)"
            return Command(update={
                "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id)]
            })

        return StructuredTool.from_function(
            name="task",
            func=_task,
            coroutine=_atask,
            description=TREE_TASK_TOOL_DESC,
            infer_schema=False,
            args_schema=TaskToolSchema,
        )

    def wrap_model_call(self, request: "ModelRequest[Any]", handler) -> "ModelResponse[Any]":
        prompt = self.system_prompt
        if prompt is None:
            return handler(request)
        from deepagents.middleware._utils import append_to_system_message
        new_system = append_to_system_message(request.system_message, prompt)
        return handler(request.override(system_message=new_system))

    async def awrap_model_call(self, request: "ModelRequest[Any]", handler) -> "ModelResponse[Any]":
        prompt = self.system_prompt
        if prompt is None:
            return await handler(request)
        from deepagents.middleware._utils import append_to_system_message
        new_system = append_to_system_message(request.system_message, prompt)
        return await handler(request.override(system_message=new_system))
