---
name: Agent orchestration config preferences
description: How the user wants OpenCode agents configured for this Blender scene generator project
type: feedback
---

User wants a production-grade multi-agent OpenCode setup using OpenAI Codex (gpt-5.3-codex) and gpt-5.4, with deep domain knowledge in each agent's system prompt.

**Why:** Project combines PySide6 GUI + Blender subprocess + Geometry Nodes + OpenAI Agents SDK pipeline. Generic prompts don't capture the cross-layer architecture rules.

**How to apply:**
- `build` is the default primary agent (gpt-5.4), delegates to specialists
- `planner` and `ai-orchestrator` get `reasoningEffort: "high"` for complex reasoning
- `core-engine` and `blender-pipeline` and `gn-specialist` use `gpt-5.3-codex` (codex-1 variant, best for Python/bpy)
- `code-review` uses `gpt-5.4-mini` (fast, read-only critic)
- Agent prompts contain actual bpy/GN code patterns, not just abstract rules
- SOTA pattern applied: ReAct reasoning in planner, actor-critic for code-review, context injection for domain knowledge
- When adding new agents: add both to opencode.jsonc AND the Agent Roster table in AGENTS.md
