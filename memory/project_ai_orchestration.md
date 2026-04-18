---
name: AI orchestration layer
description: Four-agent OpenAI pipeline added to scene_generator for generating Blender scripts from natural language
type: project
---

Added a complete AI orchestration layer at `src/proc_map_designer/ai/` in April 2026.

**Why:** User wants to drive Blender geometry node scene generation from natural language using OpenAI o-series models (Codex/o3/o4-mini).

**Architecture:** Four-agent pipeline using OpenAI Agents SDK (`openai-agents` package):
- `Planner` (o3, reasoning=high): decomposes requests, reads project state via tools
- `BlenderCoder` (o4-mini, reasoning=high): generates bpy Python batch scripts
- `GNSpecialist` (o4-mini, reasoning=high): builds Geometry Nodes trees via Python API
- `Critic` (o4-mini, reasoning=medium): validates syntax + executes in Blender, classifies errors

**Loop:** Planner → Specialist → Critic with Generate→Execute→Reflect retries (max 3), one replan on nonretriable failures.

**Token efficiency:** Three-tier context compression in `compressor.py`, golden patterns (curated bpy examples) injected into system prompts once.

**Service entry point:** `services/ai_generation_service.py` — sync wrapper using `asyncio.run()` for QThread compatibility.

**How to apply:** When user asks about adding AI features, extending agents, or debugging the AI pipeline, look at the `ai/` module structure. The `AGENTS.md` file has been updated with full documentation of the AI layer.
