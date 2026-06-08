# Agent Tree — Linux Kernel Scheduler Analysis Test Report

**Date**: 2025-06-05
**Model**: deepseek-reasoner (DeepSeek V4 Pro)
**Test Subject**: Linux kernel scheduler subsystem (kernel/sched/, ~36K lines across 6 files)
**Agent Tree Depth**: 3 levels (L0 → L1 → L2)

---

## 1. Test Configuration

| Parameter | Value |
|---|---|
| Root task | Deep-dive analysis of Linux kernel scheduler implementation |
| Tree depth | 3 (max_depth=3) |
| L1 subagents | 3 (core scheduler, CFS, RT/Deadline) |
| L2 subagents | 9 (3 per L1 branch) |
| Total nodes | 13 (1 root + 3 L1 + 9 L2) |
| Backend | FilesystemBackend(root_dir=/home/user/agent_tree/reference/linux) |
| Tools per agent | FilesystemMiddleware default tools (ls, read_file, grep, glob, write_file, edit_file) |
| Execution order | Bottom-up: L2 leaves → L1 synthesis → L0 final report |

## 2. Execution Timeline

```
[0s]     L0 spawned, task decomposed
[0s]     3× L1 spawned in parallel
[0s]     9× L2 spawned in parallel
[~120s]  First L2 completes (rt.c analysis)
[~180s]  Most L2 nodes complete
[~250s]  First L1 synthesis complete (CFS group)
[~400s]  All L1 syntheses complete
[~970s]  L0 final report delivered

Total wall time: 969.6 seconds (~16 minutes)
Nodes completed: 13/13 (100%)
```

## 3. Tree Execution Structure

```
L0: Deep-dive analysis of Linux kernel scheduler implementation
│
├── L1: Core scheduler entry points (core.c)
│   ├── L2: __schedule() function analysis ✓
│   ├── L2: pick_next_task() iteration logic ✓
│   └── L2: schedule() entry + preemption chain ✓
│
├── L1: CFS/EEVDF (fair.c)
│   ├── L2: vruntime tracking (update_curr, entity_tick) ✓
│   ├── L2: Task selection (pick_eevdf, red-black tree) ✓
│   └── L2: PELT load tracking ✓
│
└── L1: RT & Deadline (rt.c, deadline.c)
    ├── L2: SCHED_FIFO/RR implementation ✓
    ├── L2: SCHED_DEADLINE EDF + CBS ✓
    └── L2: Cross-class comparison ✓
```

## 4. Key Findings

### 4.1 Agent Tree Architecture Works Correctly

- **3-level recursion verified**: L0 spawned L1 agents, L1 agents spawned L2 agents. Each level's TreeMiddleware correctly limited depth.
- **Parallel execution confirmed**: All 9 L2 nodes ran concurrently. L1 synthesis waited for all children before proceeding.
- **Context isolation observed**: Each L2 agent analyzed only its assigned file(s). No cross-contamination of context between siblings.
- **Bottom-up synthesis functional**: L1 agents received L2 results and produced meaningful summaries. L0 synthesized 3 L1 summaries into the final report.

### 4.2 Real-World Code Analysis Quality

The final report (approximately 40 bullet points and a cross-reference table) demonstrates:

- **Accurate code analysis**: Correctly identified `schedule()` → `__schedule()` → `pick_next_task()` → `context_switch()` call chain
- **EEVDF understanding**: The agent correctly identified that Linux 6.6+ uses EEVDF (not classic CFS), described the eligibility check and deadline-based RB-tree ordering
- **PELT formula accuracy**: Correctly described the geometric decay series with 32ms half-life
- **Cross-cutting connections table**: Identified 6 cross-subsystem connections showing understanding beyond individual file analysis
- **Mode-based dispatch**: Correctly enumerated the 4 `sched_mode` values and their behavioral differences

### 4.3 Observed Issues

| Issue | Severity | Detail |
|---|---|---|
| grep timeout on large trees | Minor | grep over 63K files hits the 30s timeout. The FilesystemMiddleware's grep has a default timeout that triggers with broad patterns on the entire kernel tree |
| Listing /root permission error | Minor | Some agents attempted to list /root (permission denied). This is a FilesystemBackend behavior when agents try to explore beyond their root_dir |
| Slow with reasoning model | Expected | deepseek-reasoner spends significant time in "thinking" phase before each tool call |

## 5. Performance Metrics

| Metric | Value |
|---|---|
| Total execution time | 969.6s |
| Avg L2 leaf execution | ~120-200s each (parallel) |
| Avg L1 synthesis | ~150s each |
| L0 final synthesis | ~570s |
| Agent invocations | 13 (1 + 3 + 9) |
| LLM calls per leaf agent | ~8-15 (thinking + tool calls + response) |
| Total LLM calls estimated | ~130-180 |

## 6. Test Artifacts

- **Task file**: `/home/user/agent_tree/test_scheduler.txt`
- **Test runner**: `/home/user/agent_tree/test_run.py`
- **Target source**: `/home/user/agent_tree/reference/linux/kernel/sched/`
- **Final output**: See section "Final Report" below

## 7. Conclusion

The Agent Tree successfully executed a 3-level hierarchical analysis of the Linux kernel scheduler, involving 13 agent nodes analyzing 36,000 lines of C code. The tree structure effectively decomposed a complex task (scheduler analysis) into 9 parallel leaf tasks, synthesized into 3 intermediate reports, and finally integrated into a comprehensive final report.

This validates the core hypothesis: **hierarchical agent trees can decompose and analyze large-scale codebases that would overflow a single agent's context window.**

## Appendix: Final Report (abbreviated)

The complete L0 output is a ~50-line structured analysis covering:

1. **Core scheduling pipeline**: `schedule()` → `__schedule()` → `pick_next_task()` → `context_switch()`
2. **EEVDF implementation**: `update_curr()` vruntime, `pick_eevdf()` RB-tree with deadline ordering, PELT geometric decay
3. **Real-Time/Deadline**: SCHED_FIFO/RR O(1) bitmapped priority, SCHED_DEADLINE EDF + CBS bandwidth control, DL Fair Server starvation prevention
4. **Cross-cutting connections**: 6 connection points across subsystems identified in a comparison table

See the full test output for the complete analysis.
