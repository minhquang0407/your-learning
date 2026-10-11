# Coding Agent Integration Guide

Proven is designed as a plug-and-play **Agent Skill** for leading coding agents.

---

## 1. Quick Install via `npx skills`

Any developer or agent can install Proven using the open agent skills CLI:

```bash
# Add to current workspace
npx skills add minhquang0407/proven

# Or install globally across all agents
npx skills add minhquang0407/proven -g

# Or target a specific agent (e.g. Claude Code)
npx skills add minhquang0407/proven -a claude-code
```

---

## 2. Integration by Agent

### A. Antigravity (Google DeepMind)
Run the built-in installer:
```bash
python skills/proven/scripts/install_skill.py --target antigravity
```
Or manually copy the `skills/proven` directory to:
`~/.gemini/config/skills/proven/`

Antigravity will automatically recognize the `proven` skill and trigger it when you ask to write PR tests or verify runtime coverage.

### B. Claude Code (Anthropic)
Run:
```bash
python skills/proven/scripts/install_skill.py --target claude-code
```
Or install with `npx skills add minhquang0407/proven -a claude-code`.

Claude Code will read the `SKILL.md` instructions whenever asked to write tests for changed code.

### C. Cursor / Windsurf / Codex
1. Copy the skill into your project's `.agents/skills/proven` or reference it in your `.cursorrules` / `.windsurfrules`.
2. The agent will execute `python skills/proven/scripts/<script>.py` via its terminal execution tool.

---

## 3. Standard 7-Stage PRO Workflow

```text
Stage 1: Scan Impact & Gaps
python skills/proven/scripts/scan_impact.py

Stage 2: Get Context
python skills/proven/scripts/get_target_context.py --target FUNC:<target_name>

Stage 3: Author Behavioral Test
Agent authors tests/test_<module>.py with strong assertions

Stage 4: Verify Runtime Proof Gate
python skills/proven/scripts/verify_runtime_proof.py --target FUNC:<target_name> --test tests/test_<module>.py

Stage 5: Verify Micro-Mutation Gate (Titanium Grade)
python skills/proven/scripts/verify_runtime_proof.py --target FUNC:<target_name> --test tests/test_<module>.py --mutation-check

Stage 6: Repair Loop (If Stage 4 or 5 Fails)
Read self-healing diagnosis or mutant report, fix test, and re-verify

Stage 7: Refresh Graph & Audit
python skills/proven/scripts/refresh_runtime_map.py
```
