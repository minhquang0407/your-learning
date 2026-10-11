# Coding Agent Integration Guide

SoftGNN Advisor is designed as a plug-and-play **Agent Skill** for leading coding agents.

---

## 1. Quick Install via `npx skills`

Any developer or agent can install SoftGNN Advisor using the open agent skills CLI:

```bash
# Add to current workspace
npx skills add minhquang0407/softgnn-advisor

# Or install globally across all agents
npx skills add minhquang0407/softgnn-advisor -g

# Or target a specific agent (e.g. Claude Code)
npx skills add minhquang0407/softgnn-advisor -a claude-code
```

---

## 2. Integration by Agent

### A. Antigravity (Google DeepMind)
Run the built-in installer:
```bash
python skills/softgnn-advisor/scripts/install_skill.py --target antigravity
```
Or manually copy the `skills/softgnn-advisor` directory to:
`~/.gemini/config/skills/softgnn-advisor/`

Antigravity will automatically recognize the `softgnn-advisor` skill and trigger it when you ask to write PR tests or verify runtime coverage.

### B. Claude Code (Anthropic)
Run:
```bash
python skills/softgnn-advisor/scripts/install_skill.py --target claude-code
```
Or install with `npx skills add minhquang0407/softgnn-advisor -a claude-code`.

Claude Code will read the `SKILL.md` instructions whenever asked to write tests for changed code.

### C. Cursor / Windsurf / Codex
1. Copy the skill into your project's `.agents/skills/softgnn-advisor` or reference it in your `.cursorrules` / `.windsurfrules`.
2. The agent will execute `python skills/softgnn-advisor/scripts/<script>.py` via its terminal execution tool.

---

## 3. Standard 7-Stage PRO Workflow

```text
Stage 1: Scan Impact & Gaps
python skills/softgnn-advisor/scripts/scan_impact.py

Stage 2: Get Context
python skills/softgnn-advisor/scripts/get_target_context.py --target FUNC:<target_name>

Stage 3: Author Behavioral Test
Agent authors tests/test_<module>.py with strong assertions

Stage 4: Verify Runtime Proof Gate
python skills/softgnn-advisor/scripts/verify_runtime_proof.py --target FUNC:<target_name> --test tests/test_<module>.py

Stage 5: Verify Micro-Mutation Gate (Titanium Grade)
python skills/softgnn-advisor/scripts/verify_runtime_proof.py --target FUNC:<target_name> --test tests/test_<module>.py --mutation-check

Stage 6: Repair Loop (If Stage 4 or 5 Fails)
Read self-healing diagnosis or mutant report, fix test, and re-verify

Stage 7: Refresh Graph & Audit
python skills/softgnn-advisor/scripts/refresh_runtime_map.py
```
