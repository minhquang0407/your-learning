# Proven Runtime Proof Gate Guide

## What is the Runtime Proof Gate?

Most AI testing tools fall into a trap: they ask an LLM to generate tests, run `pytest`, and if the exit code is `0`, they assume the test is valid.

In reality:
1. **The Mocking Trap**: The LLM mocks the very function it is supposed to test, e.g. `mock.patch('my_module.my_func')`. The test passes 100%, but 0 lines of `my_func` ever run!
2. **The Shallow Assert Trap**: The test imports the module and asserts `callable(func)` or `assert True`. No logic is exercised.
3. **The Bypass Trap**: The test calls an outer entrypoint, but due to bad input data, an early return or guard bypasses the changed code.

Proven enforces the **Runtime Proof Gate**:
> **A test is ONLY accepted if it passes pytest AND dynamic tracing proves that execution passed through the target function's lines at runtime.**

---

## Proof Gate Metrics

When `verify_runtime_proof.py` (or `proven agent verify-proof`) is executed, it measures:

| Metric | Meaning | Passing Threshold |
|---|---|---|
| `pytest_passed` | Did pytest exit with code 0? | Must be `True` |
| `matching_edges` | Did runtime tracing record edges from test to target? | At least 1 edge |
| `covered_fraction` | Percentage of lines in the target function executed during test | > 0.0 (typically 50% - 100%) |
| `covered_lines` | Exact line numbers executed | Must contain core logic lines |

---

## How to Author Tests that Pass Proof Gate

1. **Import the real function**:
   ```python
   # GOOD
   from my_module import calculate_tax

   def test_calculate_tax_standard_rate():
       result = calculate_tax(amount=100.0, rate=0.1)
       assert result == 10.0
   ```
2. **Never mock the target function itself**:
   ```python
   # BAD: Target FUNC:calculate_tax will have 0 executed lines!
   @patch('my_module.calculate_tax', return_value=10.0)
   def test_calculate_tax(mock_calc):
       ...
   ```
3. **Mock heavy external I/O only**:
   Mock network, database connections, GPU/CUDA training loops, or third-party APIs if needed, but allow the target's internal branching and data transformations to execute.
4. **Use `tmp_path` for File I/O**:
   Pytest's built-in `tmp_path` fixture should always be used if files need to be written or read.

---

## Self-Healing Branch Diagnoser

When a test fails the Proof Gate (0% lines executed or stopped at a guard clause), Proven automatically returns a `self_healing` diagnosis block:

```json
{
  "proof_status": "fail",
  "self_healing": {
    "status": "diagnosed",
    "diagnosis_type": "EARLY_BRANCH",
    "branch_line": 42,
    "branch_code": "if x is None: return",
    "condition": "x is None",
    "last_executed_line": 42,
    "missed_lines_range": [43, 65],
    "explanation": "Target function branched early at line 42 due to condition `if x is None`. Main body (lines 43-65) was not executed.",
    "actionable_suggestion": "To reach the core function body (lines 43-65), provide test cases where `x is None` is False."
  }
}
```

### Supported Failure Diagnoses:
1. `MOCKED_OUT`: The target function was mocked with `@patch` or `jest.spyOn`, meaning real code was never executed. **Fix**: Remove mock on the target function.
2. `EARLY_BRANCH`: The test called the target, but stopped early at line $N$ due to a guard clause / early return. **Fix**: Provide input arguments that bypass the guard clause to execute the main body.
3. `CALLER_EARLY_BRANCH`: The test called a caller function (e.g. `checkout()`), but the caller exited before reaching `target()`. **Fix**: Provide mock data to the caller to reach the call site.
4. `NEVER_CALLED`: The target function was never referenced in the test file. **Fix**: Import and call the target directly.
5. `INPUT_GUARD_DETECTED`: 0% executed, but input validation was identified at the top of the function. **Fix**: Prepare valid mock parameters matching the function signature.

---

## Targeted Micro-Mutation Proof Gate (PRO Titanium Grade)

To prevent the **Weak Assertion Trap** (`assert res is not None`), Proven PRO injects surgical AST mutations into the target function and runs the test suite against each mutant:

```bash
python skills/proven/scripts/verify_runtime_proof.py \
  --target "FUNC:<target_name>" \
  --test "tests/test_<module>.py" \
  --mutation-check
```

### Mutators Applied:
- **Comparison Inversion**: `>` $\leftrightarrow$ `<=`, `<` $\leftrightarrow$ `>=`, `==` $\leftrightarrow$ `!=`, `is` $\leftrightarrow$ `is not`.
- **Arithmetic Flips**: `+` $\leftrightarrow$ `-`, `*` $\leftrightarrow$ `//`.
- **Boolean Negation**: `True` $\leftrightarrow$ `False`.

### Proof Grades:
- **TITANIUM PROOF**: 100% of mutants were **KILLED** (`mutants_survived == 0`). Every injected bug was caught by assertions.
- **SILVER PROOF (Weak Assertion Detected)**: One or more mutants **SURVIVED**. The test passed even though the target function was broken! The Agent must add specific value assertions to kill the survived mutants.

