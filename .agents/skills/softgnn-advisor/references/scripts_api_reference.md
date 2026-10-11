# SoftGNN Advisor — Standalone Scripts API Reference

This reference documents the CLI interface and JSON output schemas for all standalone scripts in `skills/softgnn-advisor/scripts/`.

Coding Agents (Antigravity, Claude Code, Codex, Copilot) MUST treat these scripts as black-box CLI tools.
Do NOT read or analyze internal implementation files (`agent_service.py`, `mutation_gate.py`, etc.).
All scripts support `--schema` to dump their JSON schema directly.

---

## 1. scan_impact.py

Scans Git diff or repository files to identify changed functions and detect runtime coverage gaps.

### CLI Arguments
- `--base <ref>`: Base git ref (default: `main`).
- `--head <ref>`: Head git ref (default: `HEAD`).
- `--source <auto|git|filesystem|full-scan>`: Diff detection mechanism (default: `auto`).
- `--lang <lang>`: Language override (`python`, `typescript`, `go`, etc.).
- `--fan-out`: Flag to output parallel Sub-Agent worker task batches.
- `--schema`: Output JSON schema and exit.

### Output JSON Example
```json
{
  "changed_count": 2,
  "contract_diff_count": 0,
  "missing_count": 1,
  "language": "python",
  "missing_coverage": [
    {
      "target_id": "FUNC:process_payment",
      "file": "src/payments.py",
      "risk": 0.85
    }
  ]
}
```

---

## 2. get_target_context.py

Extracts surgical AST context, enclosing signature, and call graph context for a specific function without reading the full file.

### CLI Arguments
- `--target <target_id>`: Target identifier (e.g. `FUNC:process_payment`) [Required].
- `--file <path>`: Source file path if known.
- `--schema`: Output JSON schema and exit.

### Output JSON Example
```json
{
  "target_id": "FUNC:process_payment",
  "file": "src/payments.py",
  "line_start": 10,
  "line_end": 35,
  "source_code": "def process_payment(amount, token):\n    ...",
  "callers": ["FUNC:checkout"],
  "callees": ["FUNC:gateway_charge"],
  "test_suite": "pytest"
}
```

---

## 3. verify_runtime_proof.py

Verifies runtime execution proof and runs the Titanium Micro-Mutation Gate against a target function.

### CLI Arguments
- `--target <target_id>`: Target identifier [Required].
- `--test <path>`: Path to authored test file or specific test function.
- `--pytest-args "<args>"`: Additional pytest arguments (Track 1 Native Python).
- `--lcov <path>`: Path to lcov.info / coverage.out (Track 2 Universal Engine).
- `--test-cmd "<cmd>"`: Custom test execution command (e.g. `npm test -- --coverage`).
- `--mutation-check`: Enable MicroMutationGate for Titanium mutation verification.
- `--max-mutants <int>`: Maximum AST mutants to test (default: `2`).
- `--schema`: Output JSON schema and exit.

### Output JSON Example (Success)
```json
{
  "target_id": "FUNC:process_payment",
  "proof_status": "pass",
  "covered_fraction": 1.0,
  "covered_lines": [10, 11, 12, 14, 15],
  "total_lines": 5,
  "mutation_results": {
    "killed": 2,
    "survived": 0,
    "total": 2,
    "mutation_score": 1.0
  },
  "message": "Titanium Proof achieved: 100% runtime execution and all AST mutants killed."
}
```

### Output JSON Example (Self-Healing on Branch Failure)
```json
{
  "target_id": "FUNC:process_payment",
  "proof_status": "fail",
  "covered_fraction": 0.4,
  "self_healing": {
    "status": "diagnosed",
    "diagnosis_type": "EARLY_BRANCH",
    "branch_line": 12,
    "branch_code": "if token is None: return False",
    "explanation": "Target function branched early at line 12 due to condition `token is None`.",
    "actionable_suggestion": "Provide valid mock token in test parameters to reach core logic."
  }
}
```

---

## 4. refresh_runtime_map.py

Refreshes the repository runtime coverage graph using targeted test execution or automated test discovery.

### CLI Arguments
- `--tests <path>`: Specific test file authored by the agent (e.g. `tests/test_payments.py`).
- `--pytest-args <args>`: Alias for `--tests` or additional pytest arguments.
- `--schema`: Output JSON schema and exit.

### Output JSON Example
```json
{
  "status": "success",
  "target_used": "tests/test_payments.py",
  "mode_used": "targeted_run",
  "passed_tests": 3,
  "failed_tests": 0,
  "runtime_edges_count": 14,
  "persisted": true
}
```

---

## 5. query_impact.py

Queries direct dependents and latent HGT Graph AI blast radius for a target symbol.

### CLI Arguments
- `--target <target_id>`: Target symbol ID [Required].
- `--mode <hybrid|graph|gnn>`: Analysis mode (default: `hybrid`).
- `--threshold <float>`: Confidence score threshold (default: `0.1`).
- `--schema`: Output JSON schema and exit.

---

## 6. triage_expert.py

Recommends expert reviewers and related files based on graph centrality and commit history.

### CLI Arguments
- `--query <text>`: Bug report or PR description [Required].
- `--max-devs <int>`: Maximum developer recommendations (default: `3`).
- `--max-files <int>`: Maximum related files (default: `5`).
- `--schema`: Output JSON schema and exit.

---

## 7. train_gnn.py

Triggers full-batch Heterogeneous Graph Transformer (HGT) link prediction training offline.

### CLI Arguments
- `--project <name>`: Project name override.
- `--schema`: Output JSON schema and exit.
