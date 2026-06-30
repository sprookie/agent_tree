# Agent Tree — 多层树形子代理系统设计文档

**日期**: 2025-06-05
**状态**: approved
**语言**: Python
**依赖**: deepagents SDK, langgraph, langchain, textual

---

## 1. 动机与目标

当前 agent 已能处理复杂多步任务，但面对超大规模分析场景（如 Linux 内核代码审计、数百条 commit 交叉核对、海量长文本分析）仍有瓶颈：

- **扁平子代理模型**：根 agent 直接 spawn 几十甚至上百个子代理，返回结果全部堆积在根 agent 的上下文中，根 agent 无法有效处理这么多信息
- **上下文膨胀**：每个子代理返回的中间结果占据 token 预算，根 agent 的上下文迅速耗尽

**Agent Tree 方案**：引入多层级树形结构，子代理可以有自己的子代理，信息从叶子逐层向上汇报整合。每一层只接收自己直属子节点的汇总结果，信息量逐层压缩，理论上可扩展至任意规模。

## 2. 核心创新

- **同构递归 agent 节点**：所有层 agent 结构相同，区别仅在于是否有 `task` 工具（叶子节点无）
- **自底向上执行**：叶子层先完成，父层等待所有子节点后整合
- **逐层压缩汇总**：每层父 agent 收到子节点结果后用 LLM 做一次摘要整合，只把精简报告向上传递

## 3. 项目结构

```
agent_tree/
├── src/
│   └── agent_tree/
│       ├── __init__.py            # 版本号 + 公开 API
│       ├── tree_middleware.py     # TreeMiddleware: 递归深度控制
│       ├── tree_agent.py          # create_tree_agent(): 组装入口 + 执行引擎
│       ├── tree_parser.py         # TreeParser: 缩进文本 → TreeNode
│       ├── tree_executor.py       # TreeExecutor: 自底向上执行逻辑
│       ├── tui/
│       │   ├── __init__.py
│       │   ├── app.py             # TreeApp: Textual 主应用
│       │   ├── adapter.py         # TreeUIAdapter: 流式事件 → widget
│       │   ├── widgets/
│       │   │   ├── messages.py    # TreeToolMessage, 树节点卡片
│       │   │   ├── tree_view.py   # 树形进度视图
│       │   │   └── task_input.py  # 任务输入 + 语法提示
│       │   └── styles.tcss        # Textual CSS
│       └── cli.py                 # CLI 入口
├── tests/
│   ├── test_tree_parser.py
│   ├── test_tree_agent.py
│   └── test_tree_executor.py
├── pyproject.toml
└── demo.py                        # 演示脚本
```

## 4. 核心模块设计

### 4.1 TreeParser — 缩进语法解析

**输入**：用户用缩进指定任务树

```
@tree
分析 linux kernel 调度器
  - 分析 CFS 核心逻辑
      - 关键数据结构
      - 调度入口函数
  - 分析实时调度
      - FIFO/RR 实现
```

**输出**：`TreeNode` 树结构

```python
@dataclass
class TreeNode:
    description: str      # 本节点的任务描述
    children: list[TreeNode]  # 子节点列表
    depth: int = 0        # 深度 (0=root)
    parent_idx: tuple[int, ...] | None = None  # 父节点路径，用于 TUI 渲染

class TreeParser:
    def parse(self, text: str) -> TreeNode: ...
    def parse_file(self, path: Path) -> TreeNode: ...
```

**解析规则**：
- `@tree` 开头的行触发解析模式
- 缩进层级（2 空格 / 4 空格 / tab）自动检测
- `-` 或 `*` 为列表标记（可选）
- 空行和注释行（`#`）忽略

### 4.2 TreeMiddleware — 递归子代理中间件

每个 agent 节点通过 `TreeMiddleware` 获得递归生成子代理的能力。

```python
class TreeMiddleware(AgentMiddleware):
    def __init__(
        self,
        depth: int,               # 当前节点深度 (0=root)
        max_depth: int,           # 最大深度
        model: str | BaseChatModel,
        tools: list[BaseTool],
        backend: BackendProtocol,
        tree_plan: TreeNode | None = None,  # 预设的任务树
    ): ...

    @property
    def tools(self) -> list[BaseTool]:
        if self._depth >= self._max_depth:
            return []  # 叶子：无 task 工具
        return [self._build_task_tool()]

    def _build_task_tool(self) -> BaseTool:
        """创建本层的 task 工具。
        调用时 spawn 一个 depth+1 层的子 agent。"""
        ...
```

**`_build_task_tool()` 的关键实现逻辑**：

```python
def _build_task_tool(self):
    def _task(subagent_type: str, description: str, runtime: ToolRuntime):
        child_graph = create_agent(
            self._model,
            tools=self._tools,
            middleware=[
                FilesystemMiddleware(backend=self._backend),
                TreeMiddleware(
                    depth=self._depth + 1,  # ← 递归关键：depth+1
                    max_depth=self._max_depth,
                    model=self._model,
                    tools=self._tools,
                    backend=self._backend,
                ),
            ],
            name=f"L{self._depth + 1}-{subagent_type}",
        )
        result = child_graph.invoke({
            "messages": [HumanMessage(content=description)]
        })
        # 提取最后一条非空 AIMessage
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.text and msg.text.strip():
                return Command(update={
                    "messages": [ToolMessage(content=msg.text, tool_call_id=runtime.tool_call_id)]
                })
        return Command(update={
            "messages": [ToolMessage(content="(no result)", tool_call_id=runtime.tool_call_id)]
        })

    return StructuredTool.from_function(
        name="task",
        func=_task,
        coroutine=_atask,
        description="Delegate to a sub-agent. Each sub-agent has isolated context and returns a single result.",
        args_schema=TaskToolSchema,
    )
```

**深度限制行为**：
| depth | max_depth=3 | 有 task 工具？ |
|---|---|---|
| 0 (root) | 否 | 是 → spawn L1 |
| 1 | 否 | 是 → spawn L2 |
| 2 | 否 | 是 → spawn L3 |
| 3 | 是 | **否** → 叶子 |

### 4.3 TreeExecutor — 自底向上执行引擎

当用户提供 `@tree` 语法的任务树时，执行引擎按层级顺序执行。

**设计原则**：TreeExecutor 是编排层，不直接创建 agent。它使用 `create_tree_agent()`（内部含 TreeMiddleware）创建每层的 agent 来执行任务。这样 TreeMiddleware 和 TreeExecutor 共享同一套 agent 构建逻辑，没有两个不同路径做同一件事。

```python
class TreeExecutor:
    def __init__(self, model, tools, backend, max_depth=3):
        self.model = model
        self.tools = tools
        self.backend = backend
        self.max_depth = max_depth

    async def execute(self, tree: TreeNode) -> str:
        """递归执行任务树，返回根节点的汇总结果。"""
        # 每层的 agent 都通过 create_tree_agent 构建，
        # 内部使用 TreeMiddleware 获得递归 subagent 能力
        return await self._execute_node(tree, depth=0)

    async def _execute_node(self, node: TreeNode, depth: int) -> str:
        agent = create_tree_agent(
            model=self.model,
            tools=self.tools,
            backend=self.backend,
            max_depth=self.max_depth - depth,  # 子节点只能往下 spawn 剩余深度
            current_depth=depth,
        )
        result = await agent.ainvoke({
            "messages": [HumanMessage(content=node.description)]
        })
        return result["messages"][-1].text

    # 当需要逐层汇报而不是直接让 agent 自己递归时，使用 _execute_planned:
    async def _execute_planned(self, tree: TreeNode) -> str:
        """强制按树结构逐层执行，叶子先完成再向上汇总。"""
        ...
```

**两种执行模式**：

| 模式 | 行为 | 适用场景 |
|---|---|---|
| `_execute_node` (自由) | 创建 root agent，让 TreeMiddleware 的 task 工具自主决定何时 spawn 子代理 | 无预设结构，agent 动态分解 |
| `_execute_planned` (规划) | 先执行所有叶子（并行），父节点收集子结果后做 LLM 摘要，逐层向上 | `@tree` 语法的手动指定结构 |

### 4.4 create_tree_agent — 顶层组装函数

```python
def create_tree_agent(
    model: str | BaseChatModel,
    *,
    tools: list[BaseTool] | None = None,
    backend: BackendProtocol | None = None,
    max_depth: int = 3,
    system_prompt: str | None = None,
    checkpointer: Checkpointer | None = None,
) -> CompiledStateGraph:
    """创建支持递归树形子代理的 agent。"""
    ...
```

此函数构建一个 root agent (depth=0)，其 middleware 包含：
```
TodoListMiddleware
→ FilesystemMiddleware(backend)
→ TreeMiddleware(depth=0, max_depth=max_depth, ...)
→ SummarizationMiddleware
→ PatchToolCallsMiddleware
→ MemoryMiddleware (可选)
```

### 4.5 TUI 设计

**主布局**：

```
┌─ Header ─────────────────────────────────────┐
│ agent-tree · 3 levels · claude-sonnet-4-6     │
├─ Tree Progress View ─────────────────────────┤
│                                               │
│ ╭ @tree · 分析 linux 内核调度器 ─────────────╮│
│ │                                              ││
│ │ ✓ L1 · CFS 核心  [done 12.3s]               ││
│ │ │  ├ ✓ L2 · 数据结构  [done 3.2s]           ││
│ │ │  ├ ✓ L2 · 入口函数  [done 4.1s]           ││
│ │ │  └ ✓ L2 · 负载均衡  [done 5.0s]           ││
│ │ ◷ L1 · 实时调度  [running 8.1s]              ││
│ │    ├ ✓ L2 · FIFO/RR  [done 3.5s]            ││
│ │    └ ◷ L2 · 优先级  [running 4.1s]          ││
│ │ ✗ L1 · deadline 调度  [error 2.0s]          ││
│ │   └ ✗ L2 · EDF 实现  [error]               ││
│ │                                              ││
│ ╰──────────────────────────────────────────────╯│
│                                               │
│ ══ Final Report ══════════════════════════════│
│ ## Summary                                    │
│ The Linux kernel scheduler consists of...     │
│                                               │
├─ Input ───────────────────────────────────────┤
│ $ _                                            │
└─ Status Bar ──────────────────────────────────┘
   L0: done (45s) · 32K tokens · ctrl+T tree
```

**`TreeView` widget**：用 Textual 原生组件渲染树形结构，每行包含：
- 状态图标：`✓` (done) / `◷` (running, 带微动效) / `✗` (error) / `○` (pending)
- 层级标签：`L1 · ` / `L2 · `
- 任务摘要：截断到 60 字符
- 耗时：`[done 12.3s]`
- 树形连接线：`│ ├ └` 字符

**`TaskInput` widget**：支持缩进语法高亮输入，显示实时解析预览。

## 5. 数据流

```
用户输入 @tree 语法文本
    ↓
TreeParser.parse() → TreeNode 树
    ↓
TreeExecutor.execute(tree)
    ↓
递归执行: _execute_node()
    ├─ 叶子: _run_leaf() → create_agent().ainvoke()
    ├─ 中间: asyncio.gather(所有子节点) → _summarize()
    └─ 根: 同上，最终返回完整报告
    ↓
TreeUIAdapter 接收每个节点的状态变化
    ↓
TreeView widget 更新渲染
    ↓
最终报告显示在 Output 区
```

## 6. API 用法

```python
from agent_tree import create_tree_agent, TreeParser

# 方式 1: 手工构造树并执行
agent = create_tree_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[my_search_tool, my_read_tool],
    backend=StateBackend(),
    max_depth=3,
)

result = agent.invoke({
    "messages": [HumanMessage(content="分析 linux kernel 调度器...")]
})

# 方式 2: 用 @tree 语法
tree = TreeParser.parse("""
@tree
分析 linux kernel 调度器
  - 分析 CFS 核心逻辑
      - 关键数据结构
      - 调度入口函数
  - 分析实时调度
""")

executor = TreeExecutor(model, tools, backend)
result = await executor.execute(tree)
```

## 7. 关键决策记录

| # | 决策 | 理由 |
|---|---|---|
| 1 | Python + DeepAgents SDK | 复用 middleware、filesystem、summarization 能力 |
| 2 | Agent 节点同构 | 简化实现，所有层用同一套代码 |
| 3 | 最大深度硬限制在 TreeMiddleware | 防止无限递归，每个节点只知道自己和 max_depth |
| 4 | 同级子节点并行执行 | 最大化吞吐，父节点等待所有子节点后才整合 |
| 5 | 逐层 LLM 摘要（非原始结果透传） | 控制上下文膨胀，每层只向上传递精简报告 |
| 6 | 缩进语法手动指定任务树（demo 阶段） | 先验证核心流程，自动分解作为后续迭代 |
| 7 | Textual TUI | 与 dcode 同框架，Python 原生，交互性好 |
| 8 | 轻量 TUI（不追求细节丰富） | demo 阶段聚焦核心功能，渲染树形进度就足够 |

## 8. 不在 scope 内（后续迭代）

- 自动任务分解（LLM 自己决定树结构）
- 异步子代理（长时间后台运行 + 轮询）
- 多模型混合（不同层用不同模型）
- 权限随深度衰减
- Web UI
- Thinking block 的 TUI 渲染（同 dcode，不渲染思考内容）
