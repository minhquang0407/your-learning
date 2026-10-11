"""Tri-Agent Adversarial Arena for Proven.

Orchestrates the co-evolutionary debate between:
- Author Agent (Defensive Tester)
- Adversary Agent (Semantic Bug Injector / Red Swarm)
- Critic Agent (Ground Truth Referee & Reflexion Synthesizer)

Enforces Game-Theoretic Convergence & Stopping Criteria:
1. TITANIUM_VICTORY: Nash equilibrium reached (all mutants killed, vault passed).
   Crystallizes state-transition lesson (Trap + Solution) into a LESSON node on graph.
2. MAX_ROUNDS_EXHAUSTED: Budget exhausted (default: 3 rounds).
   Flags unresolved blindspot as a VULNERABILITY node on graph.
3. STAGNATION_DETECTED: Identical surviving mutant across consecutive rounds (stops early).
4. Intermediate rounds generate transient Reflexion prompts in RAM only (no graph pollution).
"""

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from proven.core.agent_service import AgentService
from proven.core.memory_manager import GraphMemoryManager
from proven.core.mutant_vault import MutantVault
from proven.core.reflexion_engine import CausalReflexionEngine
from proven.core.swarm.red_team import RedTeamSwarm


@dataclass
class ArenaRoundResult:
    round_no: int
    target_id: str
    test_target: str
    proof_status: str
    proof_grade: str
    is_titanium: bool
    vault_status: str
    mutants_killed: int
    mutants_survived: int
    causal_reflexion: Optional[Dict[str, Any]]
    reflexion_prompt: Optional[str]
    message: str
    max_rounds: int = 3
    verdict: str = "CONTINUE"  # "TITANIUM_VICTORY", "CONTINUE", "MAX_ROUNDS_EXHAUSTED", "STAGNATION_DETECTED"
    surviving_mutant_desc: Optional[str] = None
    crystallized_lesson: Optional[Dict[str, Any]] = None
    recorded_vulnerability: Optional[Dict[str, Any]] = None
    memory_notice: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TriAgentArena:
    """Manages multi-agent adversarial evaluation and referee loop."""

    def __init__(
        self,
        repo_path: str = ".",
        project_name: Optional[str] = None,
        language: Optional[str] = None,
    ):
        self.repo_path = os.path.abspath(repo_path)
        self.svc = AgentService(project=project_name, repo_path=self.repo_path, language=language)
        self.project = self.svc.project

    def get_author_brief(self, target_id: str, source_file: Optional[str] = None) -> Dict[str, Any]:
        """Generate tailored instruction brief and ego-memory for Author Agent."""
        context = self.svc.get_context(target_id=target_id, source_file=source_file)
        memory_prompt = GraphMemoryManager.get_scoped_memory_prompt(
            target_id=target_id, repo_path=self.repo_path, project_name=self.project
        )
        return {
            "status": "success",
            "persona": "Author Agent (Defensive Tester)",
            "role": "Synthesize comprehensive, runtime-proven tests with strict behavioral assertions.",
            "target_id": target_id,
            "signature": context.get("signature"),
            "source_file": context.get("source_file"),
            "source_code": context.get("source_code"),
            "suggested_test_file": context.get("suggested_test_file"),
            "scoped_memory": memory_prompt,
            "graph_rag_context": context.get("graph_rag_prompt"),
            "directive": (
                "Write defensive tests covering happy paths, error boundaries, and state changes. "
                "Always assert exact return values and side-effects to resist adversarial mutation."
            ),
        }

    def get_adversary_brief(
        self,
        target_id: str,
        test_target: str,
        source_file: Optional[str] = None,
        swarm_personas: bool = True,
    ) -> Dict[str, Any]:
        """Generate tailored instruction brief for Adversary Agent / Red Swarm."""
        context = self.svc.get_context(target_id=target_id, source_file=source_file)
        test_content = ""
        abs_test = Path(self.repo_path) / test_target.replace("/", os.sep)
        if abs_test.exists():
            test_content = abs_test.read_text(encoding="utf-8", errors="replace")

        source_code = context.get("source_code") or ""
        use_full_swarm = RedTeamSwarm.should_scale_to_full_swarm(source_code) if swarm_personas else False

        personas_desc = (
            "Multi-Persona Red Swarm (1. Boundary & Logic, 2. State & Side-Effect, 3. Chaos & Exception)"
            if use_full_swarm
            else "Single Adversary Agent (Boundary & Logic)"
        )

        return {
            "status": "success",
            "persona": "Adversary Agent (Semantic Bugmaker)",
            "swarm_mode": personas_desc,
            "full_swarm": use_full_swarm,
            "role": "Identify specification blindspots and weak assertions in Author's test suite.",
            "target_id": target_id,
            "source_file": context.get("source_file"),
            "source_code": source_code,
            "author_test_target": test_target,
            "author_test_code": test_content[:4000],
            "graph_rag_context": context.get("graph_rag_prompt"),
            "directive": (
                "Analyze the Author's test assertions. What return attributes, side-effects, or boundary conditions are NOT verified? "
                "Formulate a subtle semantic mutation (e.g., boundary flip, nullifying side-effect statement, returning None) "
                "that alters behavior but allows the Author's test to still pass."
            ),
        }

    def referee_round(
        self,
        target_id: str,
        test_target: str,
        round_no: int = 1,
        max_rounds: int = 3,
        previous_survived_mutant: Optional[str] = None,
        pytest_args: Optional[str] = None,
    ) -> ArenaRoundResult:
        """Referee a single adversarial round between Author and Adversary.

        Enforces 3 Termination Criteria:
        1. TITANIUM_VICTORY: All mutants killed -> Crystallizes Lesson on Graph.
        2. STAGNATION_DETECTED: Consecutive identical mutant survival -> Halts early.
        3. MAX_ROUNDS_EXHAUSTED: round_no >= max_rounds -> Records VULNERABILITY on Graph.
        """
        # 1. Zero-Token Vault Regression Check
        vault_res = MutantVault.run_vault_regression(
            target_id=target_id,
            test_target=test_target,
            repo_path=self.repo_path,
            project_name=self.project,
            pytest_args=pytest_args,
        )
        vault_passed = vault_res.get("status") == "passed"
        vault_status = vault_res.get("status", "passed")

        # 2. Execute Runtime Proof Gate with Micro-Mutation Testing
        proof_res = self.svc.verify_proof(
            target_id=target_id,
            test_target=test_target,
            mutation_check=True,
            pytest_args=pytest_args,
        )

        proof_status = proof_res.get("proof_status", "fail")
        proof_grade = proof_res.get("proof_grade", "SILVER")
        mut_proof = proof_res.get("mutation_proof") or {}
        killed = mut_proof.get("mutants_killed", 0)
        survived = mut_proof.get("mutants_survived", 0)

        # Extract survived mutant description if any
        surviving_desc = None
        survived_details = mut_proof.get("details", [])
        for det in survived_details:
            if det.get("status") == "survived":
                surviving_desc = det.get("mutation") or det.get("original_code")
                break

        causal_reflexion = mut_proof.get("causal_reflexion")
        self_healing = proof_res.get("self_healing") or {}
        reflexion_prompt = self_healing.get("reflexion_prompt") or (
            causal_reflexion.get("reflexion_prompt") if causal_reflexion else None
        )

        is_titanium = (proof_status == "pass" and proof_grade == "TITANIUM" and vault_passed)
        crystallized_lesson = None
        recorded_vul = None

        # 3. Determine Game-Theoretic Verdict & State Transitions
        if is_titanium:
            verdict = "TITANIUM_VICTORY"
            final_grade = "TITANIUM"
            msg = (
                f"TITANIUM GRADE ACHIEVED in Round {round_no}! "
                f"All {killed} micro-mutants killed and all historical vault regressions passed."
            )
            # Fast learning: crystallize successful defense into a permanent LESSON node
            trap = surviving_desc or "Previous adversarial mutant variants"
            solution = f"Assert exact behavioral invariants and return state against mutants."
            rule = f"Defend `{target_id}` against boundary flips, state nullifications, and null returns."
            crystallized_lesson = GraphMemoryManager.crystallize_lesson(
                target_id=target_id,
                trap=trap,
                solution=solution,
                rule=rule,
                failure_mode="TITANIUM_DEFENSE",
                repo_path=self.repo_path,
                project_name=self.project,
            )
        elif previous_survived_mutant and surviving_desc and previous_survived_mutant == surviving_desc:
            verdict = "STAGNATION_DETECTED"
            final_grade = "SILVER"
            msg = f"Stagnation detected in Round {round_no}: Mutant `{surviving_desc}` survived consecutively. Halting early."
        elif round_no >= max_rounds:
            verdict = "MAX_ROUNDS_EXHAUSTED"
            final_grade = "SILVER" if proof_status == "pass" else "FAILED"
            msg = (
                f"Max rounds budget ({max_rounds}) exhausted in Round {round_no}. "
                f"{survived} mutant(s) survived. Flagged as known vulnerability."
            )
            # Record unresolved gap as VULNERABILITY node on graph
            recorded_vul = GraphMemoryManager.record_vulnerability(
                target_id=target_id,
                surviving_mutant_desc=surviving_desc or f"{survived} mutants survived",
                round_exhausted=round_no,
                message=msg,
                repo_path=self.repo_path,
                project_name=self.project,
            )
        else:
            verdict = "CONTINUE"
            final_grade = "SILVER" if proof_status == "pass" else "FAILED"
            reasons = []
            if survived > 0:
                reasons.append(f"{survived} mutant(s) SURVIVED (Weak assertion detected)")
            if not vault_passed:
                reasons.append(f"{vault_res.get('survived', 1)} historical vault mutant(s) SURVIVED")
            if proof_status != "pass":
                reasons.append("Test did not establish physical runtime coverage on target")
            msg = f"Round {round_no} Defeat: {'; '.join(reasons)}. Reflexion prompt generated."

        memory_notice = None
        if verdict in ("TITANIUM_VICTORY", "MAX_ROUNDS_EXHAUSTED", "STAGNATION_DETECTED"):
            trigger = GraphMemoryManager.check_sleep_trigger(
                threshold=10, repo_path=self.repo_path, project_name=self.project
            )
            if trigger.get("needs_sleep"):
                memory_notice = {
                    "needs_sleep": True,
                    "unconsolidated_count": trigger.get("unconsolidated_count", 0),
                    "threshold": trigger.get("threshold", 10),
                    "action_required": "RUN_SLEEP_CONSOLIDATION",
                    "instruction": "Run `python skills/proven/scripts/consolidate_memory.py` to synthesize repository axioms.",
                }

        return ArenaRoundResult(
            round_no=round_no,
            max_rounds=max_rounds,
            verdict=verdict,
            target_id=target_id,
            test_target=test_target,
            proof_status=proof_status,
            proof_grade=final_grade,
            is_titanium=is_titanium,
            vault_status=vault_status,
            mutants_killed=killed,
            mutants_survived=survived,
            surviving_mutant_desc=surviving_desc,
            causal_reflexion=causal_reflexion,
            reflexion_prompt=reflexion_prompt,
            crystallized_lesson=crystallized_lesson,
            recorded_vulnerability=recorded_vul,
            memory_notice=memory_notice,
            message=msg,
        )
