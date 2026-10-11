---
name: proven
description: |
  Graph-guided, runtime-proven, and mutation-verified test advisor (PRO Edition). Use when the user asks to write tests for changed code, PRs, or specific functions, find untested code changes, verify runtime proof, or enforce titanium mutation test assertions.
version: 1.0.0
author: minhquang0407
tags:
  - testing
  - pytest
  - graph-intelligence
  - runtime-proof
  - mutation-testing
  - code-coverage
---

# Proven — Agent Skill (PRO Edition)

You are paired with **Proven v1.0.0 (PRO Edition)**.

## Core Philosophy: "LLM = Author, Proven = Runtime & Behavioral Verification Gate"

- **YOU (the Agent)** are the author. You analyze code semantics, understand intent, and write/edit test files.
- **Proven** is your Scoped Runtime & Behavioral Verification Gate:
  1. It proves whether your tests **actually execute** target bytecode at runtime under test conditions (catching mock escapes and unexecuted branches).
  2. It evaluates whether assertions **catch regressions** by killing surgical AST mutations (**TITANIUM PROOF**).
  3. It diagnoses why an execution diverged or exited early (Branch Diagnoser).
  *(Bounded empirical verification: confirms bytecode execution and mutation sensitivity under tested inputs; does not assert absolute bug-free perfection).*

---

## Progressive Disclosure Index

To preserve context window efficiency, detailed guides are organized into on-demand references:

| Trigger / Situation | Read Reference | Purpose |
| :--- | :--- | :--- |
| CLI specs, input flags & JSON schemas | [`references/scripts_api_reference.md`](references/scripts_api_reference.md) | Black-box schemas for all standalone scripts (use `--schema`). |
| Multi-agent co-evolution & arena | [`references/tri_agent_arena.md`](references/tri_agent_arena.md) | Tri-Agent Adversarial Arena (Critic, Author, Adversary roles). |
| Test failed Runtime Proof or Mutation | [`references/proof_gate_guide.md`](references/proof_gate_guide.md) | Branch diagnosis codes (`EARLY_BRANCH`, `MOCKED_OUT`) & mutant kill strategies. |
| User asks for Blast Radius or Reviewer | [`references/tier2_guide.md`](references/tier2_guide.md) | Latent GNN risk prediction, Bug Triage scoring, and offline HGT training. |
| Non-Python project (TS, Go, Rust, Java) | [`references/universal_lcov_guide.md`](references/universal_lcov_guide.md) | LCOV file mapping, test command flags, and polyglot setup. |
| Agent setup / multi-agent integration | [`references/agent_integration.md`](references/agent_integration.md) | Setup for Antigravity, Claude Code, Cursor, and `skill-to-workflow`. |

> **Black-Box Agent Contract**: Treat all scripts in `skills/proven/scripts/` as black-box CLI utilities.
> NEVER inspect or analyze internal `.py` files (`agent_service.py`, `mutation_gate.py`, etc.).
> Run any script with `--schema` or consult [`references/scripts_api_reference.md`](references/scripts_api_reference.md) for JSON schemas.


---

## Standard 7-Stage PRO Workflow

```mermaid
flowchart LR
    Scan[1. SCAN<br/>Gaps] --> Context[2. CONTEXT<br/>AST & Callers]
    Context --> Author[3. AUTHOR<br/>Write tests]
    Author --> RunProof{4. RUNTIME<br/>Real execution?}
    RunProof -->|Pass| MutProof{5. MUTATION<br/>Kill mutants?}
    RunProof -->|Fail: Early Exit| Repair[6. REPAIR LOOP<br/>Branch diagnosis]
    MutProof -->|Fail: Weak Assert| Repair
    Repair --> RunProof
    MutProof -->|Pass: TITANIUM| Audit[7. FINAL AUDIT<br/>Refresh graph]
```

### Stage 1: SCAN — Find Untested Changes
```bash
python skills/proven/scripts/scan_impact.py
# Or CLI: softgnn agent scan
```
- Reads `missing_coverage`: Changed functions lacking runtime tests.
- If user specified a specific function (e.g. `FUNC:foo`), skip directly to Stage 2.

### Stage 2: CONTEXT — Surgical Code Extraction & Code GraphRAG
```bash
python skills/proven/scripts/get_target_context.py --target "FUNC:<target_name>"
# Optional: Explain GNN multi-hop attention
python skills/proven/scripts/explain_attention.py --target "FUNC:<target_name>" --visualize
```
- Extracts source code, signature, callers, callees, and repo fixture styles.
- Automatically includes **Code GraphRAG Context** (< 120 tokens): multi-hop blast radius, callee state mutations, and shared transactions to guide test assertions.

### Stage 3: AUTHOR — Write Behavioral Tests
Write into the suggested test file following **5 Golden Rules**:
1. **Import real target directly**: `from my_pkg.mod import target_func`.
2. **NEVER mock target function**: Mocking causes 0 lines executed $\rightarrow$ fails Stage 4.
3. **Mock heavy external boundaries only**: Mock network APIs, database queries, heavy GPU loops.
4. **Strong Assertions**: Check exact values, state changes, or expected exceptions (`pytest.raises`).
5. **Isolation**: Always use `tmp_path` fixture for disk operations.

### Stage 4: RUNTIME PROOF — Dynamic Tracing Verification
```bash
python skills/proven/scripts/verify_runtime_proof.py \
  --target "FUNC:<target_name>" \
  --test "tests/test_<module>.py"
```
- **`proof_status: "pass"`**: Real execution lines confirmed. Proceed to **Stage 5**.
- **`proof_status: "fail"`**: Exited early or mocked. Proceed to **Stage 6 (Repair Loop)**.

### Stage 5: MUTATION PROOF — Kill AST Mutants (PRO Titanium Gate)
```bash
python skills/proven/scripts/verify_runtime_proof.py \
  --target "FUNC:<target_name>" \
  --test "tests/test_<module>.py" \
  --mutation-check
```
- **`proof_grade: "TITANIUM"`** (`mutants_survived == 0`): All mutants killed! Proceed to **Stage 7**.
- **`proof_grade: "SILVER"`** (`mutants_survived > 0`): Weak assertion! Proceed to **Stage 6**.

### Stage 6: REPAIR LOOP — Self-Healing & Fortification
- **If Stage 4 Failed**: Read `self_healing.diagnosis` (e.g. `EARLY_BRANCH` at line 42). Adjust mock/inputs to penetrate the function body. (See [`references/proof_gate_guide.md`](references/proof_gate_guide.md)).
- **If Stage 5 Failed**: Read `survived_details`. Add specific value assertions to kill survived mutants.
- Re-verify until **TITANIUM PROOF** is achieved.

### Stage 7: FINAL AUDIT — Refresh Graph & Report
```bash
python skills/proven/scripts/refresh_runtime_map.py --tests "tests/test_<module>.py"
```
- Report completed targets, test file paths, line coverage percentage, and `TITANIUM PROOF` confirmation.

---

## Tri-Agent Adversarial Arena (Neuro-Symbolic Co-Evolution)

For safety-critical functions, invoke the **Tri-Agent Arena** where agents co-evolve via game-theoretic adversarial rounds:

```
               ┌──────────────────────────────────────────────────┐
               │       CRITIC AGENT (Supervisor / Referee)     │
               │   - Runs Bytecode Tracing & HGT Graph Topology   │
               │   - Synthesizes Causal Reflexion Diagnosis       │
               │   - Verifies Zero-Token Mutant Vault Regression   │
               └─────────────────────────┬────────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
   ┌───────────────────────────┐                   ┌───────────────────────────┐
   │   AUTHOR AGENT (Blue)  │                   │  ADVERSARY AGENT (Red) │
   │ - Synthesizes test suite  │◀──White-box Review── - Injects subtle mutants │
   │ - Reads Graph Axioms      │                   │ - Aims to bypass Author   │
   └───────────────────────────┘                   └───────────────────────────┘
```

### Tri-Agent Personas & Scripts
1. **Critic Agent (Supervisor)**: Orchestrates the rounds.
   ```bash
   python skills/proven/scripts/run_arena.py --target "FUNC:<target_name>" --test "tests/test_<mod>.py"
   ```
2. **Author Agent (Blue Team)**: Uses [`skills/proven/agents/author_agent.md`](agents/author_agent.md) to author and repair tests guided by scoped topological memory.
3. **Adversary Agent (Red Team)**: Uses [`skills/proven/agents/adversary_agent.md`](agents/adversary_agent.md) to analyze tests and craft semantic boundary mutations.

### Causal Reflexion & Topological Memory
- **Causal Reflexion Engine**: Classifies failures into `UNCOVERED_BRANCH` (bytecode miss) vs `WEAK_ASSERTION` (bytecode hit, mutant survived) and traces causal impact through HGT caller graphs.
- **Zero-Token Mutant Vault**: Killer mutants are stored in `.proven/mutant_vault/{target}/` and validated in sub-0.05s with **0 LLM tokens**.
- **Sleep Consolidation Protocol (Neocortical Abstraction)**:
  - **Trigger Detection**: When `run_arena.py` output contains `memory_notice.needs_sleep == true` (threshold >= 10 lessons), or after completing a large test suite/PR, execute the Sleep Protocol:
    1. **Cluster Lessons**: Run `python skills/proven/scripts/consolidate_memory.py`. If output returns `NEEDS_SYNTHESIS`, inspect `clusters_to_synthesize`.
    2. **Synthesize Axiom in Context**: In your reasoning, distill each cluster into exactly **one** imperative architecture rule (< 15 words) for that module.
    3. **Commit to Graph**: Execute `commit_axiom.py`:
       ```bash
       python skills/proven/scripts/commit_axiom.py \
         --cluster-id "<cluster_id>" \
         --module "<module>" \
         --rule "<distilled_rule>" \
         --lesson-ids "<id1,id2,...>"
       ```
    4. **Confirmation**: Confirm consolidated axioms and shielded lessons with the user.
    *(Offline/Manual CLI fallback: `python -m proven.cli sleep --force` or `python skills/proven/scripts/consolidate_memory.py --auto-fallback`)*.

---

## Sub-Agent Swarms & Tier 2 Intelligence

- **Parallel Fan-Out**: Run `python skills/proven/scripts/scan_impact.py --fan-out`. Process-isolated temporary sessions guarantee zero `.coverage` collisions across concurrent sub-agents.
- **Latent Blast Radius**: Run `python skills/proven/scripts/query_impact.py --target "FUNC:<id>" --mode hybrid`.
- **Reviewer Triage**: Run `python skills/proven/scripts/triage_expert.py --query "PR or bug description"`.
*(Detailed guides in [`references/tier2_guide.md`](references/tier2_guide.md) and [`references/tri_agent_arena.md`](references/tri_agent_arena.md)).*
