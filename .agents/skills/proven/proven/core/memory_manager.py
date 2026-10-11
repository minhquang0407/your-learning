"""Topological Graph-Pinned Hierarchical Memory and Sleep Consolidation for Proven.

Implements Complementary Learning Systems (CLS Theory):
- Fast Learning (Hippocampal Episodic): State transitions (Trap + Solution) are crystallized
  into local LESSON nodes upon successful mutant defeat: (FUNC) --[HAS_LESSON]--> (LESSON).
- Slow Learning (Neocortical Sleep Consolidation): Consolidates episodic lessons into parent
  AXIOM nodes: (AXIOM) --[GENERALIZES]--> (LESSON), (FUNC) --[CONSTRAINED_BY]--> (AXIOM).
- Token Shielding: Context retrieval extracts 1-hop ego-memory, querying concise AXIOM rules
  (< 80 tokens) and shielding child lessons from prompt bloat while preserving full graph lineage.
- Vulnerability Flagging: Exhausted rounds create VULNERABILITY nodes: (FUNC) --[HAS_BLINDSPOT]--> (VULNERABILITY).
"""

import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


AST_ARCHETYPES = {
    "NUMERIC_BOUNDARY_INEQUALITY": {
        "label": "Boundary Inequality",
        "default_rule": "Numeric inequality comparisons require assertions at boundary values [X-1, X, X+1] to eliminate operator mutants.",
    },
    "GUARD_CLAUSE_EARLY_RETURN": {
        "label": "Guard Early Return",
        "default_rule": "Guard clauses returning early on falsy/None require tests with valid payloads to reach the body and falsy payloads to verify fallback.",
    },
    "IN_PLACE_MUTATION": {
        "label": "In-Place Container Mutation",
        "default_rule": "In-place container mutations require verifying object state pre/post invocation and testing idempotency across multiple calls.",
    },
    "CHAOS_UNHANDLED_EXCEPTION": {
        "label": "Exception Flow",
        "default_rule": "Exception raising branches require pytest.raises assertions to verify exact exception type and error message.",
    },
}


class ASTArchetypeVisitor(ast.NodeVisitor):
    """Fast deterministic static AST visitor extracting universal software archetypes."""

    def __init__(self):
        self.archetypes = set()

    def visit_Compare(self, node):
        for op in node.ops:
            if isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn)):
                self.archetypes.add("NUMERIC_BOUNDARY_INEQUALITY")
                break
        self.generic_visit(node)

    def visit_Slice(self, node):
        self.archetypes.add("NUMERIC_BOUNDARY_INEQUALITY")
        self.generic_visit(node)

    def visit_If(self, node):
        has_return = any(isinstance(stmt, ast.Return) for stmt in node.body)
        if has_return:
            self.archetypes.add("GUARD_CLAUSE_EARLY_RETURN")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ("append", "extend", "pop", "remove", "update", "clear", "insert"):
                self.archetypes.add("IN_PLACE_MUTATION")
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, (ast.Subscript, ast.Attribute)):
                self.archetypes.add("IN_PLACE_MUTATION")
        self.generic_visit(node)

    def visit_Try(self, node):
        self.archetypes.add("CHAOS_UNHANDLED_EXCEPTION")
        self.generic_visit(node)

    def visit_Raise(self, node):
        self.archetypes.add("CHAOS_UNHANDLED_EXCEPTION")
        self.generic_visit(node)


class GraphMemoryManager:
    """Manages hierarchical knowledge graph memory, CLS consolidation, and token shielding."""

    @classmethod
    def get_memory_dir(cls, repo_path: str = ".", project_name: Optional[str] = None) -> Path:
        """Resolve memory directory location (.proven/memory in repo or global fallback)."""
        local_dir = Path(repo_path) / ".proven" / "memory"
        try:
            local_dir.mkdir(parents=True, exist_ok=True)
            return local_dir
        except Exception:
            fallback = Path.home() / ".proven" / (project_name or "default") / "memory"
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    @classmethod
    def get_axioms_file(cls, repo_path: str = ".", project_name: Optional[str] = None) -> Path:
        """Resolve path to .proven/axioms.md."""
        mem_dir = cls.get_memory_dir(repo_path, project_name)
        return mem_dir / "axioms.md"

    @classmethod
    def _get_store_file(cls, repo_path: str = ".", project_name: Optional[str] = None) -> Path:
        mem_dir = cls.get_memory_dir(repo_path, project_name)
        return mem_dir / "graph_memory.json"

    @classmethod
    def get_global_meta_file(cls) -> Path:
        """Resolve path to global meta-axioms repository (~/.proven/meta_axioms.json)."""
        try:
            global_dir = Path.home() / ".proven"
            global_dir.mkdir(parents=True, exist_ok=True)
            return global_dir / "meta_axioms.json"
        except Exception:
            fallback = Path(".proven") / "meta_axioms.json"
            fallback.parent.mkdir(parents=True, exist_ok=True)
            return fallback

    @classmethod
    def _load_global_meta(cls) -> Dict[str, Any]:
        """Load global meta-axioms list."""
        meta_file = cls.get_global_meta_file()
        if not meta_file.exists():
            return {"version": "1.0", "meta_axioms": []}
        try:
            with meta_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"version": "1.0", "meta_axioms": []}

    @classmethod
    def _save_to_global_meta(cls, new_meta_nodes: List[Dict[str, Any]]) -> None:
        """Save or update meta-axioms in global store."""
        data = cls._load_global_meta()
        existing = {m["id"]: m for m in data.get("meta_axioms", [])}
        for node in new_meta_nodes:
            existing[node["id"]] = node
        data["meta_axioms"] = list(existing.values())
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            meta_file = cls.get_global_meta_file()
            with meta_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    @classmethod
    def extract_ast_archetypes(cls, source_code: str, target_name: Optional[str] = None) -> List[str]:
        """Fast (< 0.5ms) static AST fingerprinting extracting universal software archetypes."""
        if not source_code or not source_code.strip():
            return []
        try:
            tree = ast.parse(source_code)
        except Exception:
            return []

        clean_name = target_name.split(":")[-1].split(".")[-1] if target_name else None
        target_node = None
        if clean_name:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == clean_name:
                    target_node = node
                    break

        visitor = ASTArchetypeVisitor()
        if target_node:
            visitor.visit(target_node)
        else:
            visitor.visit(tree)

        return sorted(list(visitor.archetypes))

    @classmethod
    def promote_to_meta_axioms(
        cls,
        repo_path: str = ".",
        project_name: Optional[str] = None,
        global_store: bool = True,
    ) -> Dict[str, Any]:
        """Synthesize universal META_AXIOM nodes from existing AXIOMs and persist globally."""
        data = cls._load_raw_memory(repo_path, project_name)
        nodes = data.setdefault("nodes", {})
        edges = data.setdefault("edges", [])

        axiom_nodes = [n for n in nodes.values() if n.get("type") == "AXIOM"]
        category_map = {
            "BOUNDARY_OFF_BY_ONE": "NUMERIC_BOUNDARY_INEQUALITY",
            "NULL_EMPTY_GUARD": "GUARD_CLAUSE_EARLY_RETURN",
            "STATE_MUTATION_EFFECT": "IN_PLACE_MUTATION",
            "CHAOS_UNHANDLED_EXCEPTION": "CHAOS_UNHANDLED_EXCEPTION",
            "LOGIC_INTEGRITY": "GUARD_CLAUSE_EARLY_RETURN",
        }

        by_archetype: Dict[str, List[Dict[str, Any]]] = {}
        for ax in axiom_nodes:
            cat = cls._categorize_lesson(ax)
            archetype = category_map.get(cat, "NUMERIC_BOUNDARY_INEQUALITY")
            by_archetype.setdefault(archetype, []).append(ax)

        # If no axioms yet, seed standard archetypes
        if not by_archetype and not axiom_nodes:
            for arch, meta_info in AST_ARCHETYPES.items():
                by_archetype[arch] = [{
                    "id": f"SEED_{arch}",
                    "rule": meta_info["default_rule"],
                    "label": meta_info["label"],
                }]

        now_iso = datetime.now(timezone.utc).isoformat()
        promoted = []

        for arch, ax_list in by_archetype.items():
            meta_info = AST_ARCHETYPES.get(arch, {
                "label": arch.replace("_", " ").title(),
                "default_rule": f"Enforce invariant assertions for {arch}.",
            })
            meta_id = f"META_AXIOM:{arch}"
            rule_text = meta_info["default_rule"]
            non_seed = [a for a in ax_list if not a["id"].startswith("SEED_")]
            if non_seed:
                rule_text = non_seed[0].get("rule") or rule_text

            meta_node = {
                "id": meta_id,
                "type": "META_AXIOM",
                "archetype": arch,
                "label": meta_info["label"],
                "rule": rule_text,
                "source_axioms": [a["id"] for a in ax_list],
                "source_axioms_count": len(ax_list),
                "timestamp": now_iso,
            }
            nodes[meta_id] = meta_node
            promoted.append(meta_node)

        cls._save_raw_memory(data, repo_path, project_name)

        if global_store:
            cls._save_to_global_meta(promoted)

        return {
            "status": "success",
            "promoted_count": len(promoted),
            "meta_axioms": promoted,
        }

    @classmethod
    def bind_meta_axioms_to_target(
        cls,
        target_id: str,
        source_code: str,
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """JIT/AOT: Fingerprints target function AST and automatically attaches matching META_AXIOMs."""
        archetypes = cls.extract_ast_archetypes(source_code, target_name=target_id)
        if not archetypes:
            return []

        data = cls._load_raw_memory(repo_path, project_name)
        nodes = data.setdefault("nodes", {})
        edges = data.setdefault("edges", [])

        bound = []
        for arch in archetypes:
            meta_id = f"META_AXIOM:{arch}"
            if meta_id not in nodes:
                meta_info = AST_ARCHETYPES.get(arch)
                if meta_info:
                    nodes[meta_id] = {
                        "id": meta_id,
                        "type": "META_AXIOM",
                        "archetype": arch,
                        "label": meta_info["label"],
                        "rule": meta_info["default_rule"],
                        "source_axioms_count": 1,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

            if meta_id in nodes:
                meta_node = nodes[meta_id]
                bound.append(meta_node)
                edge = {
                    "source": target_id,
                    "target": meta_id,
                    "type": "CONSTRAINED_BY",
                    "binding_mode": "AST_PATTERN_MATCH",
                    "archetype": arch,
                }
                if not any(
                    e.get("source") == target_id
                    and e.get("target") == meta_id
                    and e.get("type") == "CONSTRAINED_BY"
                    for e in edges
                ):
                    edges.append(edge)

        if bound:
            cls._save_raw_memory(data, repo_path, project_name)

        return bound

    @classmethod
    def _load_raw_memory(
        cls, repo_path: str = ".", project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load memory store, automatically upgrading legacy schema to hierarchical graph schema."""
        store_file = cls._get_store_file(repo_path, project_name)
        if not store_file.exists():
            return {
                "version": "2.0",
                "target_lessons": {},
                "nodes": {},
                "edges": [],
            }

        try:
            with store_file.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return {
                "version": "2.0",
                "target_lessons": {},
                "nodes": {},
                "edges": [],
            }

        # Check if legacy flat dictionary format
        if "version" not in raw and isinstance(raw, dict):
            migrated: Dict[str, Any] = {
                "version": "2.0",
                "target_lessons": raw,
                "nodes": {},
                "edges": [],
            }
            # Reconstruct nodes and edges from legacy records
            for tgt, lessons in raw.items():
                for item in lessons:
                    lid = item.get("lesson_id", f"LES_{hashlib.sha256(str(item).encode()).hexdigest()[:8]}")
                    node_id = f"LESSON:{lid}"
                    migrated["nodes"][node_id] = {
                        "id": node_id,
                        "type": "LESSON",
                        "target_id": tgt,
                        "lesson_id": lid,
                        "lesson": item.get("lesson", ""),
                        "trap": item.get("mutant_desc", ""),
                        "solution": item.get("lesson", ""),
                        "rule": item.get("lesson", ""),
                        "status": "unconsolidated",
                        "timestamp": item.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    }
                    migrated["edges"].append({
                        "source": tgt,
                        "target": node_id,
                        "type": "HAS_LESSON",
                    })
            return migrated

        raw.setdefault("target_lessons", {})
        raw.setdefault("nodes", {})
        raw.setdefault("edges", [])
        return raw

    @classmethod
    def _save_raw_memory(
        cls,
        data: Dict[str, Any],
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> None:
        store_file = cls._get_store_file(repo_path, project_name)
        with store_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def crystallize_lesson(
        cls,
        target_id: str,
        trap: str,
        solution: str,
        rule: str = "",
        failure_mode: str = "WEAK_ASSERTION",
        mutant_desc: str = "",
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Crystallize a state-transition lesson (Trap + Solution) into a LESSON node.

        Called ONLY when Author Agent successfully repairs tests to kill the mutant.
        """
        clean_target = target_id.strip()
        data = cls._load_raw_memory(repo_path, project_name)

        final_rule = rule.strip() or solution.strip()
        final_trap = trap.strip() or mutant_desc.strip()
        hash_seed = f"{clean_target}::{final_trap}::{solution}"
        hash_id = hashlib.sha256(hash_seed.encode("utf-8")).hexdigest()[:8]
        lesson_id = f"LES_{hash_id}"
        node_id = f"LESSON:{lesson_id}"

        now_iso = datetime.now(timezone.utc).isoformat()

        lesson_node = {
            "id": node_id,
            "type": "LESSON",
            "lesson_id": lesson_id,
            "target_id": clean_target,
            "trap": final_trap,
            "solution": solution.strip(),
            "rule": final_rule,
            "lesson": final_rule,
            "failure_mode": failure_mode,
            "mutant_desc": final_trap,
            "status": "unconsolidated",
            "timestamp": now_iso,
        }

        data["nodes"][node_id] = lesson_node

        # Ensure edge exists
        edge_exists = any(
            e.get("source") == clean_target
            and e.get("target") == node_id
            and e.get("type") == "HAS_LESSON"
            for e in data["edges"]
        )
        if not edge_exists:
            data["edges"].append({
                "source": clean_target,
                "target": node_id,
                "type": "HAS_LESSON",
            })

        # Backward compatibility target_lessons
        node_lessons = data["target_lessons"].setdefault(clean_target, [])
        for existing in node_lessons:
            if existing.get("lesson_id") == lesson_id:
                existing["timestamp"] = now_iso
                existing["rule"] = final_rule
                existing["lesson"] = final_rule
                cls._save_raw_memory(data, repo_path, project_name)
                return lesson_node

        node_lessons.append(lesson_node)
        cls._save_raw_memory(data, repo_path, project_name)
        return lesson_node

    @classmethod
    def record_vulnerability(
        cls,
        target_id: str,
        surviving_mutant_desc: str,
        round_exhausted: int = 3,
        message: str = "",
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an unresolved blindspot as a VULNERABILITY node when max rounds are exhausted."""
        clean_target = target_id.strip()
        data = cls._load_raw_memory(repo_path, project_name)

        hash_seed = f"{clean_target}::VUL::{surviving_mutant_desc}"
        hash_id = hashlib.sha256(hash_seed.encode("utf-8")).hexdigest()[:8]
        vul_id = f"VUL_{hash_id}"
        node_id = f"VULNERABILITY:{vul_id}"

        vul_node = {
            "id": node_id,
            "type": "VULNERABILITY",
            "vul_id": vul_id,
            "target_id": clean_target,
            "surviving_mutant": surviving_mutant_desc,
            "round_exhausted": round_exhausted,
            "message": message or f"Survived {round_exhausted} adversarial rounds without proof of kill.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        data["nodes"][node_id] = vul_node

        edge_exists = any(
            e.get("source") == clean_target
            and e.get("target") == node_id
            and e.get("type") == "HAS_BLINDSPOT"
            for e in data["edges"]
        )
        if not edge_exists:
            data["edges"].append({
                "source": clean_target,
                "target": node_id,
                "type": "HAS_BLINDSPOT",
            })

        cls._save_raw_memory(data, repo_path, project_name)
        return vul_node

    @classmethod
    def pin_lesson(
        cls,
        target_id: str,
        lesson: str,
        failure_mode: str = "WEAK_ASSERTION",
        mutant_desc: str = "",
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Backward-compatible helper to pin a lesson."""
        return cls.crystallize_lesson(
            target_id=target_id,
            trap=mutant_desc,
            solution=lesson,
            rule=lesson,
            failure_mode=failure_mode,
            mutant_desc=mutant_desc,
            repo_path=repo_path,
            project_name=project_name,
        )

    @classmethod
    def get_pinned_lessons(
        cls,
        target_id: str,
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve lessons pinned to a specific target node."""
        data = cls._load_raw_memory(repo_path, project_name)
        clean_target = target_id.strip()
        target_lessons = data.get("target_lessons", {})

        candidates = [clean_target, f"FUNC:{clean_target.replace('FUNC:', '')}", clean_target.replace("FUNC:", "")]
        for c in candidates:
            if c in target_lessons:
                return target_lessons[c]
        return []

    @classmethod
    def get_ego_memory_subgraph(
        cls,
        target_id: str,
        hops: int = 1,
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract the 1-hop ego-memory subgraph surrounding target_id.

        Implements Token Shielding:
        - If target has AXIOM nodes (via CONSTRAINED_BY), returns AXIOM rules.
        - Only unconsolidated LESSON nodes not yet abstracted by an Axiom are returned as active lessons.
        - Provides full provenance (child lessons under each axiom).
        """
        data = cls._load_raw_memory(repo_path, project_name)
        clean_target = target_id.strip()
        norm_target = clean_target if clean_target.startswith("FUNC:") else f"FUNC:{clean_target}"

        nodes = data.get("nodes", {})
        edges = data.get("edges", [])

        # Find connected node IDs
        connected_axiom_ids = set()
        connected_meta_axiom_ids = set()
        connected_lesson_ids = set()
        connected_vul_ids = set()

        # Check direct edges and module-level axioms
        mod_prefix = clean_target.replace("FUNC:", "").replace("CLASS:", "").split(".")[0]

        for e in edges:
            src, tgt, etype = e.get("source"), e.get("target"), e.get("type")
            if src in (clean_target, norm_target):
                if etype == "CONSTRAINED_BY" and tgt in nodes:
                    if nodes[tgt].get("type") == "META_AXIOM":
                        connected_meta_axiom_ids.add(tgt)
                    else:
                        connected_axiom_ids.add(tgt)
                elif etype == "HAS_LESSON" and tgt in nodes:
                    connected_lesson_ids.add(tgt)
                elif etype == "HAS_BLINDSPOT" and tgt in nodes:
                    connected_vul_ids.add(tgt)

        # Also find module-level axioms
        for nid, n in nodes.items():
            if n.get("type") == "AXIOM" and n.get("module") == mod_prefix:
                connected_axiom_ids.add(nid)

        active_meta_axioms = [nodes[mid] for mid in connected_meta_axiom_ids if mid in nodes]
        active_axioms = [nodes[aid] for aid in connected_axiom_ids if aid in nodes]
        active_lessons = [nodes[lid] for lid in connected_lesson_ids if lid in nodes]
        vulnerabilities = [nodes[vid] for vid in connected_vul_ids if vid in nodes]

        # Identify which lessons are already subsumed by active axioms
        subsumed_lesson_ids = set()
        for ax in active_axioms:
            for child in ax.get("generalized_lessons", []):
                subsumed_lesson_ids.add(child)

        # Unconsolidated lessons not shielded
        shielded_active_lessons = [
            les for les in active_lessons
            if les.get("status") == "unconsolidated" or les["id"] not in subsumed_lesson_ids
        ]

        return {
            "target_id": clean_target,
            "meta_axioms": active_meta_axioms,
            "axioms": active_axioms,
            "unconsolidated_lessons": shielded_active_lessons,
            "subsumed_lessons_count": len(subsumed_lesson_ids),
            "vulnerabilities": vulnerabilities,
        }

    @classmethod
    def get_scoped_memory_prompt(
        cls,
        target_id: str,
        repo_path: str = ".",
        project_name: Optional[str] = None,
        include_axioms: bool = True,
    ) -> str:
        """Build an ultra-compact (< 80 tokens) memory injection block for Author Agent using Ego-Graph."""
        ego = cls.get_ego_memory_subgraph(target_id=target_id, repo_path=repo_path, project_name=project_name)

        meta_axioms = ego.get("meta_axioms", [])
        axioms = ego["axioms"]
        lessons = ego["unconsolidated_lessons"]
        vulnerabilities = ego["vulnerabilities"]

        # Also load from axioms.md if no graph axioms found yet
        fallback_axioms = []
        if include_axioms and not axioms and not meta_axioms:
            axioms_file = cls.get_axioms_file(repo_path, project_name)
            if axioms_file.exists():
                try:
                    content = axioms_file.read_text(encoding="utf-8")
                    mod = target_id.replace("FUNC:", "").replace("CLASS:", "").split(".")[0]
                    for line in content.splitlines():
                        if line.startswith(f"- **[Axiom {mod}.") or line.startswith("- **[Axiom"):
                            fallback_axioms.append(line.strip())
                except Exception:
                    pass

        if not meta_axioms and not axioms and not fallback_axioms and not lessons and not vulnerabilities:
            return ""

        lines = ["### REPO MEMORY & AXIOMS"]

        # 1. Meta-Axioms (Top universal principles, max 1)
        if meta_axioms:
            for m_ax in meta_axioms[:1]:
                lines.append(f"- **[Meta-Axiom {m_ax.get('label')}]**: {m_ax.get('rule', '')}")

        # 2. Primary Axioms (Token Shield: at most 2 concise rules, or 1 if meta present)
        max_axioms = 1 if meta_axioms else 2
        if axioms:
            for ax in axioms[:max_axioms]:
                lines.append(f"- **[Axiom {ax.get('module', 'core')}]**: {ax.get('rule', '')}")
        elif fallback_axioms:
            for f_ax in fallback_axioms[:max_axioms]:
                lines.append(f_ax)

        # 3. Unconsolidated Episodic Lessons (at most 1 if axioms present)
        max_lessons = 1 if (meta_axioms or axioms) else 2
        if lessons:
            for p in lessons[-max_lessons:]:
                lines.append(f"- **Pinned Lesson (`{target_id}`)**: {p.get('rule') or p.get('lesson')}")

        # 4. Warning on Known Vulnerabilities
        if vulnerabilities:
            latest_vul = vulnerabilities[-1]
            lines.append(f"- **Warning: Known Blindspot**: {latest_vul.get('surviving_mutant')}")

        return "\n".join(lines)

    @classmethod
    def check_sleep_trigger(
        cls,
        threshold: int = 10,
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fast non-mutating check for unconsolidated lessons against threshold."""
        data = cls._load_raw_memory(repo_path, project_name)
        nodes = data.get("nodes", {})
        unconsolidated = [
            n for n in nodes.values()
            if n.get("type") == "LESSON" and n.get("status") == "unconsolidated"
        ]
        count = len(unconsolidated)
        return {
            "needs_sleep": count >= threshold,
            "unconsolidated_count": count,
            "threshold": threshold,
        }

    @staticmethod
    def _categorize_lesson(lesson_node: Dict[str, Any]) -> str:
        """Heuristically categorize lesson into 1 of 4 failure mode families."""
        text = " ".join([
            str(lesson_node.get("trap", "")),
            str(lesson_node.get("solution", "")),
            str(lesson_node.get("rule", "")),
            str(lesson_node.get("lesson", "")),
            str(lesson_node.get("failure_mode", "")),
        ]).lower()

        if any(w in text for w in ("boundary", "off-by-one", "<=", ">=", "<", ">", "range", "index", "slice", "length")):
            return "BOUNDARY_OFF_BY_ONE"
        if any(w in text for w in ("none", "null", "empty", "guard", "optional", "missing", "attributeerror")):
            return "NULL_EMPTY_GUARD"
        if any(w in text for w in ("state", "rollback", "side_effect", "side-effect", "cache", "mutation", "dirty")):
            return "STATE_MUTATION_EFFECT"
        if any(w in text for w in ("chaos", "exception", "raise", "crash", "typeerror", "keyerror", "unhandled")):
            return "CHAOS_UNHANDLED_EXCEPTION"
        return "LOGIC_INTEGRITY"

    @classmethod
    def cluster_unconsolidated_lessons(
        cls,
        threshold: int = 10,
        force: bool = False,
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Group unconsolidated lessons by module and failure mode family (Tier 1: Zero-Token)."""
        data = cls._load_raw_memory(repo_path, project_name)
        nodes = data.get("nodes", {})
        unconsolidated = [
            n for n in nodes.values()
            if n.get("type") == "LESSON" and n.get("status") == "unconsolidated"
        ]
        count = len(unconsolidated)

        if count == 0:
            return {
                "status": "noop",
                "message": "No unconsolidated lessons in memory.",
                "count": 0,
                "threshold": threshold,
                "clusters": [],
            }

        if count < threshold and not force:
            return {
                "status": "threshold_not_met",
                "message": f"Sample density accumulating: {count}/{threshold} lessons. Run with force=True to consolidate early.",
                "count": count,
                "threshold": threshold,
                "clusters": [],
            }

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for lnode in unconsolidated:
            tgt = lnode.get("target_id", "")
            mod = tgt.replace("FUNC:", "").replace("CLASS:", "").split(".")[0] or "general"
            category = cls._categorize_lesson(lnode)
            group_key = f"{mod}::{category}"
            grouped.setdefault(group_key, []).append(lnode)

        clusters = []
        for group_key, l_list in grouped.items():
            mod, category = group_key.split("::")
            h_seed = f"{mod}::{category}::" + "-".join(sorted(l["id"] for l in l_list))
            cluster_hash = hashlib.sha256(h_seed.encode("utf-8")).hexdigest()[:8]
            cluster_id = f"{mod}_{category.lower()}_{cluster_hash}"

            lesson_texts = [l.get("rule") or l.get("lesson") or l.get("solution") or "" for l in l_list]
            traps = [l.get("trap") or l.get("mutant_desc") or "" for l in l_list]
            targets = list(dict.fromkeys(l.get("target_id") for l in l_list if l.get("target_id")))

            clusters.append({
                "cluster_id": cluster_id,
                "module": mod,
                "category": category,
                "lesson_ids": [l["id"] for l in l_list],
                "lessons": [t for t in lesson_texts if t],
                "traps": [t for t in traps if t],
                "target_ids": targets,
                "prompt_instruction": (
                    f"Synthesize the {len(l_list)} lessons above into exactly 1 concise, imperative "
                    f"architecture rule (< 15 words) for module '{mod}'. Then call commit_axiom.py."
                ),
            })

        return {
            "status": "NEEDS_SYNTHESIS",
            "message": f"Ready to synthesize {len(clusters)} axiom clusters from {count} lessons.",
            "count": count,
            "threshold": threshold,
            "clusters": clusters,
        }

    @classmethod
    def commit_synthesized_axiom(
        cls,
        cluster_id: str,
        module: str,
        rule: str,
        lesson_ids: List[str],
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Commit an LLM/Agent synthesized Axiom into the knowledge graph (Tier 2: Knowledge Lineage)."""
        clean_rule = rule.strip()
        if not clean_rule:
            raise ValueError("Axiom rule cannot be empty.")

        data = cls._load_raw_memory(repo_path, project_name)
        nodes = data.setdefault("nodes", {})
        edges = data.setdefault("edges", [])

        now_iso = datetime.now(timezone.utc).isoformat()
        clean_cid = cluster_id.replace("AXIOM:", "").replace("AX_", "")
        axiom_node_id = f"AXIOM:AX_{clean_cid}"
        label = f"Axiom {module}.{clean_cid.split('_')[-1]}"

        axiom_node = {
            "id": axiom_node_id,
            "type": "AXIOM",
            "axiom_id": f"AX_{clean_cid}",
            "module": module,
            "label": label,
            "rule": clean_rule,
            "generalized_lessons": lesson_ids,
            "timestamp": now_iso,
        }
        nodes[axiom_node_id] = axiom_node

        for lid in lesson_ids:
            if lid in nodes:
                nodes[lid]["status"] = "consolidated"
                tgt = nodes[lid].get("target_id")
                if tgt:
                    edge_c = {"source": tgt, "target": axiom_node_id, "type": "CONSTRAINED_BY"}
                    if edge_c not in edges:
                        edges.append(edge_c)

            edge_g = {"source": axiom_node_id, "target": lid, "type": "GENERALIZES"}
            if edge_g not in edges:
                edges.append(edge_g)

        cls._save_raw_memory(data, repo_path, project_name)
        cls._sync_axioms_markdown(repo_path, project_name)

        return {
            "status": "success",
            "axiom_id": axiom_node_id,
            "module": module,
            "rule": clean_rule,
            "consolidated_lessons_count": len(lesson_ids),
        }

    @classmethod
    def _sync_axioms_markdown(
        cls,
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> Path:
        """Regenerate .proven/axioms.md from all AXIOM nodes in memory."""
        data = cls._load_raw_memory(repo_path, project_name)
        nodes = data.get("nodes", {})
        axiom_nodes = [n for n in nodes.values() if n.get("type") == "AXIOM"]

        by_module: Dict[str, List[Dict[str, Any]]] = {}
        for ax in axiom_nodes:
            mod = ax.get("module") or "general"
            by_module.setdefault(mod, []).append(ax)

        lines = [
            "# Repo-Specific Testing Axioms",
            "",
            "> Auto-generated by Proven Sleep Consolidation. These axioms are injected into Author Agent prompts.",
            "",
        ]

        for mod, a_list in sorted(by_module.items()):
            lines.append(f"### Module: `{mod}`")
            for ax in a_list:
                lbl = ax.get("label") or f"Axiom {mod}"
                lines.append(f"- **[{lbl}]**: {ax.get('rule', '')}")
            lines.append("")

        axioms_file = cls.get_axioms_file(repo_path, project_name)
        axioms_file.write_text("\n".join(lines), encoding="utf-8")
        return axioms_file

    @classmethod
    def consolidate_axioms(
        cls,
        repo_path: str = ".",
        project_name: Optional[str] = None,
        threshold: int = 10,
        force: bool = True,
        meta_promote: bool = False,
    ) -> Dict[str, Any]:
        """Sleep Consolidation (Neocortical Abstraction):

        1. Groups unconsolidated episodic lessons by module/target.
        2. Promotes them into parent AXIOM nodes: (AXIOM) --[GENERALIZES]--> (LESSON).
        3. Constrains targets: (FUNC) --[CONSTRAINED_BY]--> (AXIOM).
        4. Marks constituent lessons as status='consolidated'.
        5. Writes .proven/axioms.md and persists hierarchical knowledge graph.
        6. Optionally promotes axioms to universal META_AXIOM nodes.
        """
        data = cls._load_raw_memory(repo_path, project_name)
        nodes = data.setdefault("nodes", {})
        edges = data.setdefault("edges", [])

        # Collect all LESSON nodes
        lesson_nodes = [n for n in nodes.values() if n.get("type") == "LESSON"]
        unconsolidated = [n for n in lesson_nodes if n.get("status") == "unconsolidated"]

        if not lesson_nodes:
            if meta_promote:
                meta_res = cls.promote_to_meta_axioms(repo_path, project_name)
                return {
                    "status": "success",
                    "message": f"Promoted {meta_res.get('promoted_count', 0)} meta-axioms.",
                    "total_axioms": 0,
                    "promoted_meta_count": meta_res.get("promoted_count", 0),
                }
            return {
                "status": "noop",
                "message": "No pinned lessons to consolidate.",
                "total_axioms": 0,
            }

        if len(unconsolidated) < threshold and not force and unconsolidated:
            return {
                "status": "threshold_not_met",
                "message": f"Sample density accumulating: {len(unconsolidated)}/{threshold} lessons.",
                "count": len(unconsolidated),
                "threshold": threshold,
            }

        # Group by module
        by_module: Dict[str, List[Dict[str, Any]]] = {}
        for lnode in lesson_nodes:
            tgt = lnode.get("target_id", "")
            mod = tgt.replace("FUNC:", "").replace("CLASS:", "").split(".")[0] or "general"
            by_module.setdefault(mod, []).append(lnode)

        now_iso = datetime.now(timezone.utc).isoformat()
        total_axioms = 0
        new_axiom_nodes = {}
        new_edges = []

        for mod, l_list in by_module.items():
            rule_map: Dict[str, List[str]] = {}
            for lnode in l_list:
                rule_text = lnode.get("rule") or lnode.get("lesson") or ""
                if rule_text:
                    rule_map.setdefault(rule_text, []).append(lnode["id"])

            for idx, (rule_text, child_lesson_ids) in enumerate(list(rule_map.items())[:5], start=1):
                total_axioms += 1
                axiom_id = f"AXIOM:AX_{mod}_{idx}"
                label = f"Axiom {mod}.{idx}"

                axiom_node = {
                    "id": axiom_id,
                    "type": "AXIOM",
                    "axiom_id": f"AX_{mod}_{idx}",
                    "module": mod,
                    "label": label,
                    "rule": rule_text,
                    "generalized_lessons": child_lesson_ids,
                    "timestamp": now_iso,
                }
                new_axiom_nodes[axiom_id] = axiom_node

                for clid in child_lesson_ids:
                    new_edges.append({
                        "source": axiom_id,
                        "target": clid,
                        "type": "GENERALIZES",
                    })
                    if clid in nodes:
                        nodes[clid]["status"] = "consolidated"

                for clid in child_lesson_ids:
                    cl_target = nodes.get(clid, {}).get("target_id")
                    if cl_target:
                        new_edges.append({
                            "source": cl_target,
                            "target": axiom_id,
                            "type": "CONSTRAINED_BY",
                        })

        for aid, anode in new_axiom_nodes.items():
            nodes[aid] = anode

        for ne in new_edges:
            if not any(
                e.get("source") == ne["source"]
                and e.get("target") == ne["target"]
                and e.get("type") == ne["type"]
                for e in edges
            ):
                edges.append(ne)

        cls._save_raw_memory(data, repo_path, project_name)
        axioms_file = cls._sync_axioms_markdown(repo_path, project_name)

        promoted_meta_count = 0
        if meta_promote:
            meta_res = cls.promote_to_meta_axioms(repo_path, project_name)
            promoted_meta_count = meta_res.get("promoted_count", 0)

        return {
            "status": "success",
            "message": f"Consolidated {len(lesson_nodes)} lessons into {total_axioms} axioms in {axioms_file.name}.",
            "total_axioms": total_axioms,
            "axioms_file": str(axioms_file),
            "modules": list(by_module.keys()),
            "promoted_meta_count": promoted_meta_count,
        }

    @classmethod
    def export_memory_graph(
        cls,
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Export memory graph nodes and edges for Cytoscape visualization."""
        data = cls._load_raw_memory(repo_path, project_name)
        return {
            "nodes": list(data.get("nodes", {}).values()),
            "edges": list(data.get("edges", [])),
        }
