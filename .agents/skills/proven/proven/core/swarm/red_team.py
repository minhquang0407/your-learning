"""Parallel Multi-Persona Red Team (Adversarial Swarm) for Proven.

Implements three distinct attack personas to overcome single-agent cognitive blindspots:
1. RedBoundaryAgent ("Boundary & Logic Hacker"):
   Inverts comparison operators (<, >, ==, !=), flips booleans (and/or), off-by-one arithmetic.
2. RedStateAgent ("Side-Effect & State Saboteur"):
   Deletes side-effects, state mutations, cache evictions, database rollbacks, event emissions.
3. RedChaosAgent ("Chaos & Exception Poisoner"):
   Injects None returns, empty collections, type mismatches, and unhandled exception paths.

Features dynamic swarm scaling based on target complexity and HGT blast radius.
"""

import ast
import copy
from dataclasses import asdict, dataclass
import os
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SwarmMutant:
    mutant_id: str
    persona: str
    line: int
    mutation_type: str
    description: str
    original_snippet: str
    mutated_snippet: str
    mutated_tree: Optional[ast.AST] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("mutated_tree", None)
        return d


class RedBoundaryAgent:
    """Exploits condition operators, relational boundaries, and boolean logic."""

    NAME = "RedBoundaryAgent"
    ROLE = "Boundary & Logic Hacker"

    COMPARE_OPS = {
        ast.Eq: (ast.NotEq, "== -> !="),
        ast.NotEq: (ast.Eq, "!= -> =="),
        ast.Gt: (ast.LtE, "> -> <="),
        ast.LtE: (ast.Gt, "<= -> >"),
        ast.Lt: (ast.GtE, "< -> >="),
        ast.GtE: (ast.Lt, ">= -> <"),
    }

    BOOL_OPS = {
        ast.And: (ast.Or, "and -> or"),
        ast.Or: (ast.And, "or -> and"),
    }

    @classmethod
    def attack(cls, tree: ast.AST, target_node: ast.FunctionDef, max_mutants: int = 2) -> List[SwarmMutant]:
        mutants = []
        for node in ast.walk(target_node):
            if len(mutants) >= max_mutants:
                break

            # 1. Comparison operations
            if isinstance(node, ast.Compare):
                for idx, op in enumerate(node.ops):
                    op_type = type(op)
                    if op_type in cls.COMPARE_OPS:
                        new_op_cls, desc = cls.COMPARE_OPS[op_type]
                        tree_copy = copy.deepcopy(tree)
                        # Locate corresponding node in copy
                        for sub in ast.walk(tree_copy):
                            if isinstance(sub, ast.Compare) and getattr(sub, "lineno", None) == node.lineno:
                                if idx < len(sub.ops):
                                    sub.ops[idx] = new_op_cls()
                                    mutants.append(SwarmMutant(
                                        mutant_id=f"MUT_BOUND_{len(mutants)+1}",
                                        persona=cls.NAME,
                                        line=getattr(node, "lineno", 1),
                                        mutation_type="BOUNDARY_INVERSION",
                                        description=f"Inverted comparison: {desc}",
                                        original_snippet=ast.unparse(node),
                                        mutated_snippet=ast.unparse(sub),
                                        mutated_tree=tree_copy,
                                    ))
                                    break
                        if len(mutants) >= max_mutants:
                            break

            # 2. Boolean operations
            elif isinstance(node, ast.BoolOp):
                op_type = type(node.op)
                if op_type in cls.BOOL_OPS:
                    new_op_cls, desc = cls.BOOL_OPS[op_type]
                    tree_copy = copy.deepcopy(tree)
                    for sub in ast.walk(tree_copy):
                        if isinstance(sub, ast.BoolOp) and getattr(sub, "lineno", None) == node.lineno:
                            sub.op = new_op_cls()
                            mutants.append(SwarmMutant(
                                mutant_id=f"MUT_BOUND_{len(mutants)+1}",
                                persona=cls.NAME,
                                line=getattr(node, "lineno", 1),
                                mutation_type="BOOLEAN_FLIP",
                                description=f"Flipped boolean operator: {desc}",
                                original_snippet=ast.unparse(node),
                                mutated_snippet=ast.unparse(sub),
                                mutated_tree=tree_copy,
                            ))
                            break

        return mutants


class RedStateAgent:
    """Targets state mutations, side-effects, cache evictions, and transactions."""

    NAME = "RedStateAgent"
    ROLE = "Side-Effect & State Saboteur"

    @classmethod
    def _get_stmt_lists(cls, root: ast.AST) -> List[List[ast.stmt]]:
        lists = []
        for node in ast.walk(root):
            if hasattr(node, "body") and isinstance(node.body, list):
                lists.append(node.body)
            if hasattr(node, "orelse") and isinstance(node.orelse, list):
                lists.append(node.orelse)
            if hasattr(node, "finalbody") and isinstance(node.finalbody, list):
                lists.append(node.finalbody)
        return lists

    @classmethod
    def attack(cls, tree: ast.AST, target_node: ast.FunctionDef, max_mutants: int = 2) -> List[SwarmMutant]:
        mutants = []
        containers = cls._get_stmt_lists(target_node)

        for stmt_list in containers:
            for stmt in stmt_list:
                if len(mutants) >= max_mutants:
                    break

                # 1. Target expression statements (function/method calls with potential side-effects)
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    call_repr = ast.unparse(stmt.value)
                    tree_copy = copy.deepcopy(tree)
                    matched = False
                    for copy_stmts in cls._get_stmt_lists(tree_copy):
                        for s_idx, s_node in enumerate(copy_stmts):
                            if isinstance(s_node, ast.Expr) and getattr(s_node, "lineno", None) == getattr(stmt, "lineno", None):
                                copy_stmts[s_idx] = ast.Pass()
                                matched = True
                                break
                        if matched:
                            break

                    if matched:
                        mutants.append(SwarmMutant(
                            mutant_id=f"MUT_STATE_{len(mutants)+1}",
                            persona=cls.NAME,
                            line=getattr(stmt, "lineno", 1),
                            mutation_type="SIDE_EFFECT_NULLIFICATION",
                            description=f"Nullified statement `{call_repr}` with `pass`",
                            original_snippet=call_repr,
                            mutated_snippet="pass",
                            mutated_tree=tree_copy,
                        ))

                # 2. Target augmented assignments (e.g. balance -= amount, count += 1)
                elif isinstance(stmt, ast.AugAssign):
                    aug_repr = ast.unparse(stmt)
                    tree_copy = copy.deepcopy(tree)
                    matched = False
                    for copy_stmts in cls._get_stmt_lists(tree_copy):
                        for s_idx, s_node in enumerate(copy_stmts):
                            if isinstance(s_node, ast.AugAssign) and getattr(s_node, "lineno", None) == getattr(stmt, "lineno", None):
                                copy_stmts[s_idx] = ast.Pass()
                                matched = True
                                break
                        if matched:
                            break

                    if matched:
                        mutants.append(SwarmMutant(
                            mutant_id=f"MUT_STATE_{len(mutants)+1}",
                            persona=cls.NAME,
                            line=getattr(stmt, "lineno", 1),
                            mutation_type="STATE_MUTATION_OMISSION",
                            description=f"Suppressed state mutation `{aug_repr}` with `pass`",
                            original_snippet=aug_repr,
                            mutated_snippet="pass",
                            mutated_tree=tree_copy,
                        ))

        return mutants


class RedChaosAgent:
    """Injects None returns, empty collections, and unhandled boundary paths."""

    NAME = "RedChaosAgent"
    ROLE = "Chaos & Exception Poisoner"

    @classmethod
    def attack(cls, tree: ast.AST, target_node: ast.FunctionDef, max_mutants: int = 2) -> List[SwarmMutant]:
        mutants = []
        for stmt in ast.walk(target_node):
            if len(mutants) >= max_mutants:
                break

            # Target Return statements: change return value to None or empty container
            if isinstance(stmt, ast.Return) and stmt.value is not None:
                ret_repr = ast.unparse(stmt)
                tree_copy = copy.deepcopy(tree)
                for sub in ast.walk(tree_copy):
                    if isinstance(sub, ast.Return) and getattr(sub, "lineno", None) == stmt.lineno:
                        sub.value = ast.Constant(value=None)
                        mutants.append(SwarmMutant(
                            mutant_id=f"MUT_CHAOS_{len(mutants)+1}",
                            persona=cls.NAME,
                            line=getattr(stmt, "lineno", 1),
                            mutation_type="CHAOS_RETURN_NULL",
                            description="Poisoned return expression to `return None`",
                            original_snippet=ret_repr,
                            mutated_snippet="return None",
                            mutated_tree=tree_copy,
                        ))
                        break

        return mutants


class RedTeamSwarm:
    """Coordinates the Parallel Multi-Persona Red Team."""

    PERSONAS = {
        "boundary": RedBoundaryAgent,
        "state": RedStateAgent,
        "chaos": RedChaosAgent,
    }

    @classmethod
    def should_scale_to_full_swarm(
        cls,
        source_code: str,
        blast_radius: float = 0.0,
        complexity_threshold: int = 2,
    ) -> bool:
        """Dynamically decide whether to deploy the full 3-persona swarm.

        Deploy full swarm if:
        - Target has high blast radius (> 0.4)
        - Target has high branching / line count (> 10 lines or >= 2 branch statements)
        """
        if blast_radius > 0.4:
            return True
        lines = [line.strip() for line in source_code.splitlines() if line.strip()]
        if len(lines) > 10:
            return True
        branch_keywords = sum(
            any(line.startswith(kw) for kw in ("if ", "elif ", "else:", "for ", "while ", "try:", "except"))
            for line in lines
        )
        return branch_keywords >= complexity_threshold

    @classmethod
    def generate_swarm_mutants(
        cls,
        original_code: str,
        target_name: str,
        full_swarm: bool = True,
        max_per_persona: int = 2,
    ) -> List[SwarmMutant]:
        """Aggregate mutants from active Red Personas, deduplicating equivalent mutations."""
        try:
            tree = ast.parse(original_code)
        except Exception:
            return []

        target_node = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target_name:
                target_node = node
                break

        if not target_node:
            return []

        active_personas = list(cls.PERSONAS.values()) if full_swarm else [RedBoundaryAgent]
        all_mutants: List[SwarmMutant] = []
        seen_diffs = set()

        for persona in active_personas:
            p_mutants = persona.attack(tree, target_node, max_mutants=max_per_persona)
            for m in p_mutants:
                diff_key = f"{m.line}::{m.original_snippet}::{m.mutated_snippet}"
                if diff_key not in seen_diffs:
                    seen_diffs.add(diff_key)
                    all_mutants.append(m)

        return all_mutants
