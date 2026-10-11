# Tri-Agent Adversarial Arena & Neuro-Symbolic Co-Evolution

This guide details the architecture, personas, and execution protocol for the **Proven Tri-Agent Arena**.

---

## 1. Architecture Overview

Traditional test generation relies on single-agent loops with weak surface-level feedback. The Proven Arena models test synthesis as a **Neuro-Symbolic Non-Zero-Sum Game**:

```
               ┌──────────────────────────────────────────────────┐
               │       CRITIC AGENT (Supervisor / Referee)     │
               │   - Dynamic Bytecode Tracing (Coverage Gate)     │
               │   - HGT Heterogeneous Graph Topology (Causal AST)│
               │   - Micro-Mutation Verification & Mutant Vault   │
               │   - Causal Reflexion Diagnostic Synthesis        │
               └─────────────────────────┬────────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
   ┌───────────────────────────┐                   ┌───────────────────────────┐
   │   AUTHOR AGENT (Blue)  │                   │  ADVERSARY AGENT (Red) │
   │ - Persona: author_agent   │◀──White-box Review── - Persona: adversary_agent│
   │ - Goal: Bulletproof Tests │                   │ - Goal: Inject Semantic   │
   │ - Reads: Scoped Axioms    │                   │   Mutants that survive    │
   └───────────────────────────┘                   └───────────────────────────┘
```

### The Three Personas
1. **Critic Agent (Supervisor / Referee)**:
   - Embodied by the Primary Coding Agent (Antigravity, Claude Code, Cursor) using `skills/proven/scripts/run_arena.py`.
   - Never writes tests or code directly; acts as impartial ground truth.
   - Evaluates real bytecode line execution and AST mutant survival.
   - Uses HGT caller topology to explain causal failure impact.

2. **Author Agent (Blue Team)**:
   - Defined in [`skills/proven/agents/author_agent.md`](../agents/author_agent.md).
   - Responsible for crafting robust unit and integration tests with invariant assertions.
   - Conditioned by repository axioms and graph-pinned lessons (< 80 tokens).

3. **Adversary Agent (Red Team)**:
   - Defined in [`skills/proven/agents/adversary_agent.md`](../agents/adversary_agent.md).
   - Examines Author's authored test code (white-box) to identify logical blindspots and unasserted side effects.
   - Proposes surgical AST mutants (e.g. boundary conditions, off-by-one, negated comparisons) to break tests.

---

## 2. Adversarial Execution Protocol

### Step 1: Initialize Arena Round
The Critic Agent initializes the arena round:
```bash
python skills/proven/scripts/run_arena.py \
  --target "FUNC:process_payment" \
  --test "tests/test_payments.py" \
  --round 1
```

Output includes:
- Target function source code and line bounds.
- In-context memory (`pinned_lessons` and `scoped_axioms`).
- Vault regression status (whether previous killer mutants still pass).
- Author brief ready to hand off to Author Agent.

### Step 2: Author Agent Writes/Refines Tests
Critic invokes or delegates to Author Agent with the `author_brief`. Author adheres to the 5 Golden Rules:
1. Direct target import (no mocking target itself).
2. Deep invariant assertions (state changes, return values, exception structures).
3. Respecting scoped repository axioms.

### Step 3: Adversary Agent Proposes Mutants
Critic invokes or delegates to Adversary Agent with the `adversary_brief` containing:
- Target function source code.
- Authored test file.
Adversary identifies the weakest assertion boundary and drafts candidate AST mutations.

### Step 4: Referee Evaluation & Causal Reflexion
Critic evaluates the round:
```bash
python skills/proven/scripts/run_arena.py \
  --target "FUNC:process_payment" \
  --test "tests/test_payments.py" \
  --round 1 \
  --mutation-check
```

If mutants survive or coverage is partial:
- **Causal Reflexion Engine** distinguishes:
  - `UNCOVERED_BRANCH`: Target bytecode line was never hit by test execution.
  - `WEAK_ASSERTION`: Target bytecode line was executed, but mutant was not killed by assertions.
- **Topological Impact**: Traces upstream callers via AST/HGT graph to assess ripple effect.
- **Zero-Token Mutant Vault**: Persists surviving mutants to `.proven/mutant_vault/FUNC:process_payment/`.
- **Topological Memory Pinning**: Pinned lesson stored in memory for this target node.

### Step 5: Iteration & Convergence
Author receives the Reflexion prompt, repairs assertions, and the round repeats until:
- **`verdict: "TITANIUM_VICTORY"`** (100% execution, 0 surviving mutants, 0 vault regressions).

---

## 3. Zero-Token Mutant Vault

Killer mutants discovered during adversarial rounds are automatically archived in:
`.proven/mutant_vault/<target_id>/mutant_<hash>.json`

On every subsequent verification or arena run:
1. `MutantVault` loads all saved killer mutants.
2. Applies each AST diff in memory and runs pytest.
3. Verifies that test suite fails (mutant is killed) in **< 0.05s**.
4. Consumes **0 LLM tokens** for regression verification.

---

## 4. Sleep Consolidation

To prevent long-term context window pollution:
1. Node-specific lessons are pinned locally to AST graph nodes in `.proven/memory.json`.
2. When query context is fetched, only the top-2 relevant lessons are injected (< 80 tokens overhead).
3. Periodic sleep consolidation aggregates episodic lessons into timeless architectural rules:
```bash
python skills/proven/scripts/consolidate_memory.py
```
Consolidated rules are appended to `.proven/axioms.md` and read by future Author sessions.
