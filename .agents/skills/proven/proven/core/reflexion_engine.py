"""Causal Reflexion Engine for Proven.

Combines symbolic execution tracing with topological code graphs to diagnose
failure mechanisms when mutants survive (weak assertions vs uncovered branches)
and synthesizes actionable Reflexion Memory for Coding Agents.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CausalReflexion:
    target_id: str
    failure_mode: str  # "WEAK_ASSERTION" | "UNCOVERED_BRANCH"
    mutant_id: int
    mutated_line: int
    mutation_desc: str
    original_code: str
    mutated_code: Optional[str]
    execution_status: str  # "HIT" | "MISSED"
    downstream_callers: List[Dict[str, Any]]
    causal_root_cause: str
    actionable_directive: str
    reflexion_prompt: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CausalReflexionEngine:
    """Diagnoses surviving mutants by joining execution traces with graph topology."""

    @classmethod
    def diagnose(
        cls,
        target_id: str,
        mutant_info: Dict[str, Any],
        covered_lines: List[int],
        repo_path: str = ".",
        graph_repo: Optional[Any] = None,
        round_no: int = 1,
    ) -> CausalReflexion:
        """Diagnose why a mutant survived and synthesize an actionable reflexion prompt.

        Args:
            target_id: The identifier of the mutated target (e.g., 'FUNC:calculate_total').
            mutant_info: Dictionary containing line, mutation, original_code, and optional mutated_code.
            covered_lines: Set or list of line numbers executed by the test during runtime proof.
            repo_path: Path to the root repository.
            graph_repo: Optional GraphRepository instance to query topological callers.
            round_no: Current iteration round in the multi-agent co-evolution loop.
        """
        line_no = int(mutant_info.get("line", 0))
        mutation_desc = str(mutant_info.get("mutation", "Mutation applied"))
        orig_code = str(mutant_info.get("original_code", "")).strip()
        mut_code = mutant_info.get("mutated_code")
        if mut_code is not None:
            mut_code = str(mut_code).strip()
        mut_id = int(mutant_info.get("mutant_id", 1))

        # 1. Physical Bytecode Trace Verification
        executed = line_no in covered_lines if covered_lines else False
        if executed:
            failure_mode = "WEAK_ASSERTION"
            execution_status = "HIT"
            causal_root_cause = (
                f"Line {line_no} was physically executed under the mutated condition ({mutation_desc}: `{orig_code}`), "
                f"but the test suite passed anyway without raising an AssertionError. "
                "The test does not assert the exact output, return state, or side-effects produced by this code."
            )
            actionable_directive = (
                f"Strengthen test assertions to explicitly check the exact return value or state mutated at line {line_no}. "
                "Avoid loose assertions such as 'is not None', '>= 0', or ignoring returned attributes."
            )
        else:
            failure_mode = "UNCOVERED_BRANCH"
            execution_status = "MISSED"
            causal_root_cause = (
                f"Line {line_no} ({orig_code}) was NOT executed by any test in the test suite. "
                "The test inputs failed to satisfy the branch conditions or guard clauses leading into this block."
            )
            actionable_directive = (
                f"Add targeted test cases providing input data that satisfies the branch conditions leading to line {line_no}."
            )

        # 2. Topological Graph Impact (Callers & Ripple Propagation)
        downstream_callers = cls._extract_topological_impact(target_id, graph_repo)

        # 3. Synthesize In-Context Reflexion Prompt (Markdown)
        reflexion_prompt = cls._build_markdown_prompt(
            target_id=target_id,
            round_no=round_no,
            line_no=line_no,
            mutation_desc=mutation_desc,
            orig_code=orig_code,
            mut_code=mut_code,
            execution_status=execution_status,
            failure_mode=failure_mode,
            downstream_callers=downstream_callers,
            causal_root_cause=causal_root_cause,
            actionable_directive=actionable_directive,
        )

        return CausalReflexion(
            target_id=target_id,
            failure_mode=failure_mode,
            mutant_id=mut_id,
            mutated_line=line_no,
            mutation_desc=mutation_desc,
            original_code=orig_code,
            mutated_code=mut_code,
            execution_status=execution_status,
            downstream_callers=downstream_callers,
            causal_root_cause=causal_root_cause,
            actionable_directive=actionable_directive,
            reflexion_prompt=reflexion_prompt,
        )

    @classmethod
    def _extract_topological_impact(
        cls, target_id: str, graph_repo: Optional[Any]
    ) -> List[Dict[str, Any]]:
        """Query callers and ripple effects from GraphRepository if available."""
        impact = []
        if not graph_repo:
            return impact

        try:
            g = getattr(graph_repo, "graph", None)
            if g is not None and hasattr(g, "predecessors"):
                nodes = getattr(g, "nodes", {})
                clean_candidates = [
                    target_id,
                    f"FUNC:{target_id.replace('FUNC:', '')}",
                    target_id.replace("FUNC:", ""),
                ]
                found_target = None
                for candidate in clean_candidates:
                    try:
                        if candidate in g or (isinstance(nodes, dict) and candidate in nodes):
                            found_target = candidate
                            break
                    except Exception:
                        if isinstance(nodes, dict) and candidate in nodes:
                            found_target = candidate
                            break

                if found_target:
                    callers = list(g.predecessors(found_target))
                    for caller in callers[:5]:
                        node_data = nodes.get(caller, {}) if isinstance(nodes, dict) else {}
                        impact.append({
                            "caller_id": caller,
                            "node_type": node_data.get("type", "Function") if isinstance(node_data, dict) else "Function",
                            "risk_score": 0.85,
                            "relation": "direct_caller",
                        })
        except Exception:
            pass

        return impact

    @classmethod
    def _build_markdown_prompt(
        cls,
        target_id: str,
        round_no: int,
        line_no: int,
        mutation_desc: str,
        orig_code: str,
        mut_code: Optional[str],
        execution_status: str,
        failure_mode: str,
        downstream_callers: List[Dict[str, Any]],
        causal_root_cause: str,
        actionable_directive: str,
    ) -> str:
        """Render a formatted, high-signal Reflexion memory block for Author Agent."""
        lines = [
            f"### CRITIC REFLEXION MEMORY (Round {round_no} Defeat)",
            f"- **Target Node**: `{target_id}`",
            f"- **Mutant Injected**: Line {line_no} ({mutation_desc})",
            f"  - Original: `{orig_code}`",
        ]
        if mut_code:
            lines.append(f"  - Mutated:  `{mut_code}`")

        lines.extend([
            f"- **Physical Trace**: {execution_status} (Line {line_no} was {'executed by test' if execution_status == 'HIT' else 'never reached'})",
            f"- **Failure Mode**: `{failure_mode}`",
        ])

        if downstream_callers:
            lines.append("- **Topological Ripple Risk**:")
            for caller in downstream_callers:
                lines.append(f"  - `{caller.get('caller_id')}` (Risk Score: {caller.get('risk_score', 0.8):.2f})")

        lines.extend([
            "- **Causal Root Cause**:",
            f"  {causal_root_cause}",
            "- **Actionable Directive for Author Agent**:",
            f"  {actionable_directive}",
        ])

        return "\n".join(lines)
