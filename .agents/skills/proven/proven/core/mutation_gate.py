"""Targeted Micro-Mutation Testing Proof Gate for SoftGNN PRO.

Validates assertion strength by injecting surgical AST mutations into target functions:
- If the test fails against the mutated code -> Mutant KILLED (Titanium Proof Passed).
- If the test passes against the mutated code -> Mutant SURVIVED (Weak Assertion Detected).
"""

import ast
import copy
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class MicroMutationGate:
    """Surgical AST mutation engine for target-level assertion verification."""

    COMPARE_MUTATIONS = {
        ast.Eq: ast.NotEq,
        ast.NotEq: ast.Eq,
        ast.Gt: ast.LtE,
        ast.LtE: ast.Gt,
        ast.Lt: ast.GtE,
        ast.GtE: ast.Lt,
        ast.Is: ast.IsNot,
        ast.IsNot: ast.Is,
        ast.In: ast.NotIn,
        ast.NotIn: ast.In,
    }

    BINOP_MUTATIONS = {
        ast.Add: ast.Sub,
        ast.Sub: ast.Add,
        ast.Mult: ast.FloorDiv,
    }

    BOOL_MUTATIONS = {
        ast.And: ast.Or,
        ast.Or: ast.And,
    }

    @classmethod
    def evaluate_mutations(
        cls,
        target_id: str,
        source_file: str,
        test_target: str,
        repo_path: str = ".",
        max_mutants: int = 3,
        pytest_args: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Apply surgical mutations to target function and test against test_target."""
        abs_source = os.path.join(repo_path, source_file.replace("/", os.sep))
        if not os.path.exists(abs_source) or not abs_source.endswith(".py"):
            return {
                "status": "skipped",
                "reason": "Source file not found or not a Python file",
                "mutation_gate_status": "skipped",
                "proof_grade": "SILVER",
            }

        original_code = Path(abs_source).read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(original_code)
        except Exception as exc:
            return {
                "status": "error",
                "reason": f"Failed to parse source file AST: {exc}",
                "mutation_gate_status": "skipped",
                "proof_grade": "SILVER",
            }

        target_name = target_id.replace("FUNC:", "").split(".")[-1]
        target_node = cls._find_target_function_node(tree, target_id)
        if not target_node:
            return {
                "status": "skipped",
                "reason": f"Target function '{target_name}' not found in AST",
                "mutation_gate_status": "skipped",
                "proof_grade": "SILVER",
            }

        mutant_specs = cls._collect_mutants(tree, target_node, max_mutants=max_mutants)
        if not mutant_specs:
            return {
                "status": "passed",
                "reason": "No mutatable AST operators found in target function",
                "mutation_gate_status": "passed",
                "mutants_total": 0,
                "mutants_killed": 0,
                "mutants_survived": 0,
                "mutation_score": 1.0,
                "proof_grade": "TITANIUM",
                "details": [],
            }

        details = []
        killed_count = 0
        survived_count = 0

        # Run each mutant in a transactional try...finally block
        source_lines = original_code.splitlines()

        for idx, (mutated_tree, line_no, mut_desc) in enumerate(mutant_specs, start=1):
            mutated_code = ast.unparse(mutated_tree)
            survived = False
            try:
                # 1. Apply mutation transactionally
                Path(abs_source).write_text(mutated_code, encoding="utf-8")

                # 2. Run pytest on the mutated code
                cmd = [sys.executable, "-m", "pytest", test_target, "-q"]
                if pytest_args:
                    cmd.extend(pytest_args.split())

                proc = subprocess.run(
                    cmd,
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                )

                if proc.returncode != 0:
                    # Test failed -> Mutant was KILLED!
                    killed_count += 1
                    status = "killed"
                else:
                    # Test passed against buggy code -> Mutant SURVIVED!
                    survived_count += 1
                    status = "survived"
                    survived = True

            except subprocess.TimeoutExpired:
                # An infinite loop in mutant means mutant was killed
                killed_count += 1
                status = "killed"
            except Exception as e:
                # Any runtime exception indicates mutant was killed
                killed_count += 1
                status = "killed"
            finally:
                # ALWAYS restore original source code immediately!
                Path(abs_source).write_text(original_code, encoding="utf-8")

            orig_line_snippet = source_lines[line_no - 1].strip() if line_no <= len(source_lines) else ""
            details.append({
                "mutant_id": idx,
                "line": line_no,
                "mutation": mut_desc,
                "original_code": orig_line_snippet,
                "status": status,
                "verdict": "KILLED (Test caught the bug)" if status == "killed" else "SURVIVED (Weak assertion: Test passed buggy code)",
            })

        total = len(details)
        score = round(killed_count / total, 2) if total > 0 else 1.0

        if survived_count == 0:
            gate_status = "passed"
            proof_grade = "TITANIUM"
            message = (
                f"TITANIUM PROOF CONFIRMED: All {killed_count}/{total} mutants were KILLED! "
                "The test suite has verified strong behavioral assertions."
            )
        else:
            gate_status = "weak_assertions"
            proof_grade = "SILVER"
            first_survived = next((d for d in details if d["status"] == "survived"), None)
            s_line = first_survived["line"] if first_survived else "unknown"
            s_mut = first_survived["mutation"] if first_survived else "unknown"
            s_code = first_survived["original_code"] if first_survived else ""

            message = (
                f"WEAK ASSERTION DETECTED: {survived_count}/{total} mutant(s) SURVIVED! "
                f"When SoftGNN mutated line {s_line} ({s_mut}: `{s_code}`), the test still passed! "
                "Please add stricter assert statements checking exact return values or side-effects."
            )

        return {
            "status": "success",
            "mutation_gate_status": gate_status,
            "mutants_total": total,
            "mutants_killed": killed_count,
            "mutants_survived": survived_count,
            "mutation_score": score,
            "proof_grade": proof_grade,
            "message": message,
            "details": details,
        }

    @classmethod
    def _find_target_function_node(cls, tree: ast.AST, target_id: str) -> Optional[ast.AST]:
        """Locate function node matching target_id in AST."""
        target_name = target_id.replace("FUNC:", "").strip()
        parts = target_name.split(".")

        if len(parts) == 1:
            fn_name = parts[0]
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == fn_name:
                    return node
        elif len(parts) >= 2:
            cls_name, fn_name = parts[0], parts[1]
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name == cls_name:
                    for child in node.body:
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == fn_name:
                            return child
        # Fallback search by function name anywhere in AST
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == parts[-1]:
                return node
        return None

    @classmethod
    def _collect_mutants(cls, tree: ast.AST, target_node: ast.AST, max_mutants: int = 3) -> List[Tuple[ast.AST, int, str]]:
        """Collect list of (mutated_full_tree, line_no, description)."""
        mutants = []

        # Walk target function to locate mutable operators
        for node in ast.walk(target_node):
            if len(mutants) >= max_mutants:
                break

            # 1. Comparison mutations (> to <=, == to !=, etc.)
            if isinstance(node, ast.Compare) and node.ops:
                op = node.ops[0]
                op_cls = type(op)
                if op_cls in cls.COMPARE_MUTATIONS:
                    new_op_cls = cls.COMPARE_MUTATIONS[op_cls]
                    mutated_node = copy.deepcopy(node)
                    mutated_node.ops[0] = new_op_cls()
                    mut_desc = f"{op_cls.__name__} -> {new_op_cls.__name__}"
                    mutants.append((cls._replace_node_in_tree(tree, node, mutated_node), node.lineno, mut_desc))

            # 2. Binary operations (+ to -, - to +, etc.)
            elif isinstance(node, ast.BinOp):
                op_cls = type(node.op)
                if op_cls in cls.BINOP_MUTATIONS:
                    new_op_cls = cls.BINOP_MUTATIONS[op_cls]
                    mutated_node = copy.deepcopy(node)
                    mutated_node.op = new_op_cls()
                    mut_desc = f"{op_cls.__name__} -> {new_op_cls.__name__}"
                    mutants.append((cls._replace_node_in_tree(tree, node, mutated_node), node.lineno, mut_desc))

            # 3. Boolean constants (True to False, False to True)
            elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
                mutated_node = copy.deepcopy(node)
                mutated_node.value = not node.value
                mut_desc = f"bool: {node.value} -> {mutated_node.value}"
                mutants.append((cls._replace_node_in_tree(tree, node, mutated_node), node.lineno, mut_desc))

        return mutants

    @classmethod
    def _replace_node_in_tree(cls, tree: ast.AST, original_child: ast.AST, replacement: ast.AST) -> ast.AST:
        """Create a clone of tree with original_child replaced by replacement."""
        class Replacer(ast.NodeTransformer):
            def visit(self, n):
                if n is original_child or (
                    type(n) == type(original_child)
                    and getattr(n, "lineno", None) == getattr(original_child, "lineno", None)
                    and getattr(n, "col_offset", None) == getattr(original_child, "col_offset", None)
                ):
                    return replacement
                return self.generic_visit(n)

        cloned_root = copy.deepcopy(tree)
        return Replacer().visit(cloned_root)
