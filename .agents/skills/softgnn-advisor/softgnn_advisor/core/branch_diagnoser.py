"""Branch and early-exit diagnoser for Self-Healing Proof Gate.

Analyzes why a test failed to achieve runtime proof for a target function:
1. Detects if target was mocked out in the test file.
2. Identifies early-exit branch points / guard clauses (e.g. `if x is None: return`).
3. Checks if a caller function branched out before reaching the target.
4. Generates actionable mock data hints for Coding Agents.
"""

import ast
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class BranchDiagnoser:
    """Diagnoses runtime execution failures and branch cutoffs."""

    MOCK_PATTERNS = [
        re.compile(r'@patch\s*\(\s*["\']([^"\']+)["\']'),
        re.compile(r'patch\s*\(\s*["\']([^"\']+)["\']'),
        re.compile(r'mocker\.patch\s*\(\s*["\']([^"\']+)["\']'),
        re.compile(r'monkeypatch\.setattr\s*\(\s*["\']([^"\']+)["\']'),
        re.compile(r'jest\.spyOn\s*\([^,]+,\s*["\']([^"\']+)["\']'),
        re.compile(r'vi\.spyOn\s*\([^,]+,\s*["\']([^"\']+)["\']'),
    ]

    GUARD_PATTERNS_MULTILANG = [
        re.compile(r'^\s*if\s*\((.+?)\)\s*(?:return|throw|raise)?'),
        re.compile(r'^\s*if\s+(.+?)\s*\{\s*(?:return|throw)?'),
        re.compile(r'^\s*if\s+(.+?):\s*(?:return|raise)?'),
    ]

    @classmethod
    def diagnose_failure(
        cls,
        target_id: str,
        source_file: str,
        test_file: Optional[str] = None,
        covered_lines: Optional[List[int]] = None,
        function_range: Optional[List[int]] = None,
        all_covered_files: Optional[Dict[str, Set[int]]] = None,
        repo_path: str = ".",
    ) -> Dict[str, Any]:
        """Produce deep diagnosis and actionable healing suggestions."""
        covered = sorted(covered_lines or [])
        target_name = target_id.replace("FUNC:", "").split(".")[-1]

        abs_source = os.path.join(repo_path, source_file.replace("/", os.sep))
        source_lines: List[str] = []
        if os.path.exists(abs_source):
            try:
                source_lines = Path(abs_source).read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                pass

        test_lines: List[str] = []
        if test_file:
            abs_test = os.path.join(repo_path, test_file.replace("/", os.sep))
            if os.path.exists(abs_test):
                try:
                    test_lines = Path(abs_test).read_text(encoding="utf-8", errors="replace").splitlines()
                except Exception:
                    pass

        # 1. Check if Target was Mocked Out in Test File
        if test_lines and len(covered) == 0:
            mock_diag = cls._check_mocking(target_name, test_lines, test_file or "")
            if mock_diag:
                return mock_diag

        # 2. Check if Target was called but branched early (Early Return / Guard Clause)
        if function_range and len(function_range) == 2 and source_lines:
            start_line, end_line = function_range
            fn_total_lines = max(1, end_line - start_line + 1)

            # Case A: Partial execution (hit some lines, but stopped early before core logic)
            if 0 < len(covered) < fn_total_lines:
                branch_diag = cls._diagnose_early_branch(
                    target_name, source_lines, covered, start_line, end_line, abs_source
                )
                if branch_diag:
                    return branch_diag

            # Case B: Zero lines executed
            if len(covered) == 0:
                # Check if caller function in all_covered_files branched before calling target
                if all_covered_files:
                    caller_diag = cls._check_caller_early_branch(target_name, all_covered_files, repo_path)
                    if caller_diag:
                        return caller_diag

                # Check if test file even contains target_name
                if test_lines and not any(target_name in l for l in test_lines):
                    return {
                        "status": "diagnosed",
                        "diagnosis_type": "NEVER_CALLED",
                        "target_id": target_id,
                        "explanation": f"Target function '{target_name}' was never referenced or called in test file '{test_file or 'test'}'.",
                        "actionable_suggestion": f"Import and directly call '{target_name}(...)' with valid test parameters in your test case.",
                    }

                # Check if the target function itself starts with an input guard clause
                guard_hint = cls._detect_first_guard(target_name, source_lines, start_line, end_line)
                if guard_hint:
                    return guard_hint

        # Fallback default diagnosis
        return {
            "status": "diagnosed",
            "diagnosis_type": "UNREACHED",
            "target_id": target_id,
            "explanation": f"Target function '{target_name}' was not executed during test run (0 lines covered).",
            "actionable_suggestion": f"Ensure your test invokes '{target_name}' directly and provides parameters satisfying initial guard clauses.",
        }

    @classmethod
    def _check_mocking(cls, target_name: str, test_lines: List[str], test_file: str) -> Optional[Dict[str, Any]]:
        """Detect if target was mocked in test file."""
        for idx, line in enumerate(test_lines, start=1):
            for pat in cls.MOCK_PATTERNS:
                match = pat.search(line)
                if match:
                    mocked_target = match.group(1)
                    if target_name in mocked_target:
                        return {
                            "status": "diagnosed",
                            "diagnosis_type": "MOCKED_OUT",
                            "line_number": idx,
                            "line_code": line.strip(),
                            "explanation": (
                                f"Detected that target function '{target_name}' is mocked at line {idx} in '{test_file}' "
                                f"(`{line.strip()}`). When mocked, target bytecode is bypassed, resulting in 0% runtime coverage."
                            ),
                            "actionable_suggestion": (
                                f"Remove mock on target '{target_name}'. Only mock external dependencies (APIs, databases, networks) to allow real execution."
                            ),
                        }
        return None

    @classmethod
    def _diagnose_early_branch(
        cls,
        target_name: str,
        source_lines: List[str],
        covered: List[int],
        start_line: int,
        end_line: int,
        abs_source: str,
    ) -> Optional[Dict[str, Any]]:
        """Identify exact branch point / guard clause where execution stopped."""
        last_line = max(covered)

        # 1. Try Python AST inspection for high precision
        if abs_source.endswith(".py"):
            ast_diag = cls._inspect_python_ast_branch(source_lines, last_line, start_line, end_line, target_name)
            if ast_diag:
                return ast_diag

        # 2. Heuristic line search backwards from last_line
        search_min = max(start_line, last_line - 3)
        for lno in range(last_line, search_min - 1, -1):
            if lno - 1 < len(source_lines):
                line_str = source_lines[lno - 1]
                for gpat in cls.GUARD_PATTERNS_MULTILANG:
                    m = gpat.search(line_str)
                    if m:
                        cond = m.group(1).strip()
                        missed_start = last_line + 1
                        missed_count = max(0, end_line - missed_start + 1)
                        return {
                            "status": "diagnosed",
                            "diagnosis_type": "EARLY_BRANCH",
                            "branch_line": lno,
                            "branch_code": line_str.strip(),
                            "condition": cond,
                            "last_executed_line": last_line,
                            "missed_lines_range": [missed_start, end_line],
                            "missed_lines_count": missed_count,
                            "explanation": (
                                f"Target function '{target_name}' branched early at line {lno} due to condition `{line_str.strip()}`. "
                                f"Main body (lines {missed_start}-{end_line}, {missed_count} lines) was not executed."
                            ),
                            "actionable_suggestion": (
                                f"To reach the core function body (lines {missed_start}-{end_line}), "
                                f"provide mock data or arguments negating the exit condition (`{cond}`)."
                            ),
                        }

        # If no explicit if found, return line cutoff
        missed_start = last_line + 1
        return {
            "status": "diagnosed",
            "diagnosis_type": "EARLY_EXIT",
            "last_executed_line": last_line,
            "missed_lines_range": [missed_start, end_line],
            "explanation": (
                f"Target function '{target_name}' stopped execution at line {last_line}. "
                f"Remaining lines ({missed_start}-{end_line}) were not reached by test inputs."
            ),
            "actionable_suggestion": f"Add test cases with inputs that branch past line {last_line} to reach the function body.",
        }

    @classmethod
    def _inspect_python_ast_branch(
        cls,
        source_lines: List[str],
        last_line: int,
        start_line: int,
        end_line: int,
        target_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Use Python AST to find the exact enclosing or preceding If condition."""
        source_text = "\n".join(source_lines)
        try:
            tree = ast.parse(source_text)
        except Exception:
            return None

        # Find all ast.If nodes in the target function range
        if_nodes: List[ast.If] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                n_end = getattr(node, "end_lineno", node.lineno)
                if start_line <= node.lineno <= end_line:
                    if_nodes.append(node)

        # Sort by line number
        if_nodes.sort(key=lambda n: n.lineno)

        # Find the If node that covers or immediately precedes last_line
        matched_if: Optional[ast.If] = None
        for inode in if_nodes:
            i_end = getattr(inode, "end_lineno", inode.lineno)
            # Either last_line is the If itself, or inside the If body (like a return or raise)
            if inode.lineno <= last_line <= i_end:
                matched_if = inode
                break
            # Or last_line is right before this If node
            if inode.lineno == last_line or inode.lineno == last_line - 1:
                matched_if = inode

        if matched_if:
            try:
                cond_str = ast.unparse(matched_if.test)
            except Exception:
                cond_str = "condition"

            branch_line = matched_if.lineno
            branch_code = source_lines[branch_line - 1].strip() if branch_line <= len(source_lines) else f"if {cond_str}:"
            missed_start = last_line + 1
            missed_count = max(0, end_line - missed_start + 1)

            # Check if there is an early return inside body
            has_return = any(isinstance(stmt, (ast.Return, ast.Raise)) for stmt in matched_if.body)
            action_hint = (
                f"To reach the core function body (lines {missed_start}-{end_line}), "
                f"provide test inputs where condition `{cond_str}` does not trigger an early exit."
            )

            return {
                "status": "diagnosed",
                "diagnosis_type": "EARLY_BRANCH",
                "branch_line": branch_line,
                "branch_code": branch_code,
                "condition": cond_str,
                "last_executed_line": last_line,
                "missed_lines_range": [missed_start, end_line],
                "missed_lines_count": missed_count,
                "explanation": (
                    f"Execution branched early at line {branch_line} due to `{branch_code}`. "
                    f"Core body (lines {missed_start}-{end_line}) was not reached."
                ),
                "actionable_suggestion": action_hint,
            }

        return None

    @classmethod
    def _check_caller_early_branch(
        cls,
        target_name: str,
        all_covered_files: Dict[str, Set[int]],
        repo_path: str,
    ) -> Optional[Dict[str, Any]]:
        """Check if a caller function executed up to an early branch before calling target."""
        for file_rel, covered_set in all_covered_files.items():
            abs_f = os.path.join(repo_path, file_rel.replace("/", os.sep))
            if not os.path.exists(abs_f) or not abs_f.endswith(".py"):
                continue
            try:
                content = Path(abs_f).read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(content)
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check if this function calls target_name
                    calls_target = False
                    call_lineno = None
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Call):
                            call_name = ""
                            if isinstance(sub.func, ast.Name):
                                call_name = sub.func.id
                            elif isinstance(sub.func, ast.Attribute):
                                call_name = sub.func.attr
                            if call_name == target_name:
                                calls_target = True
                                call_lineno = sub.lineno
                                break

                    if calls_target and call_lineno:
                        # Check if caller function was executed, but execution stopped before call_lineno
                        fn_end = getattr(node, "end_lineno", node.lineno)
                        fn_covered = [l for l in covered_set if node.lineno <= l <= fn_end]
                        if fn_covered and max(fn_covered) < call_lineno:
                            last_caller_line = max(fn_covered)
                            flines = content.splitlines()

                            # Find enclosing If statement in caller
                            branch_line = last_caller_line
                            for sub in ast.walk(node):
                                if isinstance(sub, ast.If):
                                    i_end = getattr(sub, "end_lineno", sub.lineno)
                                    if sub.lineno <= last_caller_line <= i_end:
                                        branch_line = sub.lineno
                                        break

                            branch_code = flines[branch_line - 1].strip() if branch_line <= len(flines) else ""
                            return {
                                "status": "diagnosed",
                                "diagnosis_type": "CALLER_EARLY_BRANCH",
                                "caller_name": node.name,
                                "caller_file": file_rel,
                                "branch_line": branch_line,
                                "branch_code": branch_code,
                                "call_line": call_lineno,
                                "last_executed_line": last_caller_line,
                                "explanation": (
                                    f"Target '{target_name}' was not reached because caller '{node.name}' in '{file_rel}' "
                                    f"exited early at line {branch_line} (`{branch_code}`) before call site at line {call_lineno}."
                                ),
                                "actionable_suggestion": (
                                    f"Provide parameters/mock data for caller '{node.name}' to bypass early exit at line {last_caller_line}."
                                ),
                            }
        return None

    @classmethod
    def _detect_first_guard(
        cls,
        target_name: str,
        source_lines: List[str],
        start_line: int,
        end_line: int,
    ) -> Optional[Dict[str, Any]]:
        """Detect guard clauses at the beginning of target function."""
        check_limit = min(start_line + 6, end_line)
        for lno in range(start_line, check_limit + 1):
            if lno - 1 < len(source_lines):
                line = source_lines[lno - 1]
                for gpat in cls.GUARD_PATTERNS_MULTILANG:
                    m = gpat.search(line)
                    if m:
                        cond = m.group(1).strip()
                        return {
                            "status": "diagnosed",
                            "diagnosis_type": "INPUT_GUARD_DETECTED",
                            "branch_line": lno,
                            "branch_code": line.strip(),
                            "condition": cond,
                            "explanation": f"Target function '{target_name}' has an input validation guard at line {lno}: `{line.strip()}`.",
                            "actionable_suggestion": f"Ensure test inputs satisfy condition `{cond}` to avoid early guard exit.",
                        }
        return None
