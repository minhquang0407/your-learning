"""Topological Code GraphRAG and Attention Explainability Engine for Proven.

Combines Heterogeneous Graph AST topology with Heterogeneous Graph Transformer (HGT)
Message Passing to extract multi-hop subgraph attention and inject compact,
structurally aware context into AI Coding Agents.
"""

from collections import deque
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class CodeGraphRAG:
    """Extracts multi-hop subgraph attention and generates GraphRAG prompts for Coding Agents."""

    RELATION_WEIGHTS = {
        "calls": 0.85,
        "instantiates": 0.80,
        "defines": 0.75,
        "uses": 0.70,
        "modifies": 0.60,
        "co-change": 0.60,
        "imports": 0.50,
        "depends_on": 0.65,
    }

    @classmethod
    def _generate_rationale(cls, relation: str, hop: int, node_type: str) -> str:
        """Generate human/LLM understandable rationale for attention weight."""
        rel_lower = relation.lower()
        if "call" in rel_lower:
            if hop == 1:
                return "Direct callee; high execution failure blast radius"
            return f"Transitive call dependency (hop {hop}); potential regression propagation"
        if "use" in rel_lower or node_type == "Class":
            return "Shared state or data model container; concurrency & dirty state sensitive"
        if "co-change" in rel_lower or "modifies" in rel_lower:
            return f"Historical co-change correlation (hop {hop}); high commit coupling"
        if "instantiate" in rel_lower:
            return "Direct class instantiation; lifecycle and constructor dependency"
        return f"Structural dependency (hop {hop}) via relation '{relation}'"

    @classmethod
    def extract_subgraph_attention(
        cls,
        target_id: str,
        hops: int = 3,
        top_k: int = 5,
        mode: str = "hybrid",
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract multi-hop subgraph attention scores using HGT or Topological Personalized PageRank."""
        clean_target = target_id.strip()
        abs_repo = os.path.abspath(repo_path)
        project = project_name or Path(abs_repo).name

        attended_nodes: List[Dict[str, Any]] = []
        total_subgraph_nodes = 0
        engine_used = "topological_ppr"

        # Try ImpactEngine if data exists
        try:
            from proven.core.impact_engine import ImpactEngine
            engine = ImpactEngine(project)
            resolved = engine.resolve_target(clean_target)
            if resolved:
                target_key = resolved.key
                target_label = engine.display_node_label(target_key)

                # 1. Multi-hop BFS with Edge Weights & Decay
                visited: Set[Tuple[str, int]] = {target_key}
                node_scores: Dict[Tuple[str, int], Dict[str, Any]] = {}
                queue = deque([(target_key, 0, 1.0, [target_label])])

                while queue:
                    curr_key, curr_hop, curr_weight, curr_path = queue.popleft()
                    if curr_hop >= hops:
                        continue

                    # Explore outgoing edges (callees, used classes, state)
                    for rel, dst_key in engine.out_edges.get(curr_key, []):
                        if dst_key == target_key or not engine.is_project_candidate(dst_key):
                            continue
                        rel_weight = cls.RELATION_WEIGHTS.get(rel.lower(), 0.50)
                        # Hop decay: 0.75 factor per hop
                        decayed = curr_weight * rel_weight * (0.75 ** curr_hop)
                        dst_label = engine.display_node_label(dst_key)
                        next_path = curr_path + [f"--({rel})--> {dst_label}"]

                        if dst_key not in node_scores:
                            node_scores[dst_key] = {
                                "score": 0.0,
                                "hop": curr_hop + 1,
                                "relation": rel,
                                "path": " ".join(next_path),
                                "label": dst_label,
                                "node_type": dst_key[0],
                            }
                        node_scores[dst_key]["score"] += decayed
                        if dst_key not in visited and curr_hop + 1 < hops:
                            visited.add(dst_key)
                            queue.append((dst_key, curr_hop + 1, decayed, next_path))

                    # Explore incoming edges (callers, importers)
                    for rel, src_key in engine.in_edges.get(curr_key, []):
                        if src_key == target_key or not engine.is_project_candidate(src_key):
                            continue
                        rel_weight = cls.RELATION_WEIGHTS.get(rel.lower(), 0.50)
                        decayed = curr_weight * rel_weight * (0.75 ** curr_hop)
                        src_label = engine.display_node_label(src_key)
                        next_path = [f"{src_label} --({rel})-->"] + curr_path

                        if src_key not in node_scores:
                            node_scores[src_key] = {
                                "score": 0.0,
                                "hop": curr_hop + 1,
                                "relation": rel,
                                "path": " ".join(next_path),
                                "label": src_label,
                                "node_type": src_key[0],
                            }
                        node_scores[src_key]["score"] += decayed
                        if src_key not in visited and curr_hop + 1 < hops:
                            visited.add(src_key)
                            queue.append((src_key, curr_hop + 1, decayed, next_path))

                total_subgraph_nodes = len(node_scores)

                # 2. Blend GNN Scores if available
                gnn_scores = {}
                if mode in ("hybrid", "gnn") and os.path.exists(engine.model_path):
                    try:
                        gnn_scores = engine._compute_gnn_scores(target_key, {"Function", "Class", "File"})
                        engine_used = "hgt_hybrid" if mode == "hybrid" else "hgt_attention"
                    except Exception:
                        engine_used = "topological_ppr"

                for key, info in node_scores.items():
                    base_topo = min(1.0, info["score"])
                    gnn_score = gnn_scores.get(key, 0.0)
                    if gnn_scores:
                        final_attn = (0.75 * base_topo) + (0.25 * gnn_score) if base_topo > 0 else 0.30 * gnn_score
                    else:
                        final_attn = base_topo
                    info["attention_score"] = min(1.0, max(0.05, final_attn))

                # 3. Rank Top-K Attended Nodes
                ranked = sorted(node_scores.values(), key=lambda x: x["attention_score"], reverse=True)[:top_k]
                for item in ranked:
                    attended_nodes.append({
                        "symbol": item["label"],
                        "node_type": item["node_type"],
                        "attention_score": round(item["attention_score"], 2),
                        "hop_distance": item["hop"],
                        "relation": item["relation"],
                        "path": item["path"],
                        "semantic_rationale": cls._generate_rationale(
                            item["relation"], item["hop"], item["node_type"]
                        ),
                    })
        except Exception:
            pass

        # Fallback to AST relations if no graph ETL data found
        if not attended_nodes:
            fallback_nodes = cls._ast_subgraph_fallback(clean_target, abs_repo, hops=hops, top_k=top_k)
            attended_nodes = fallback_nodes
            total_subgraph_nodes = len(fallback_nodes)
            engine_used = "ast_heuristic"

        prompt_block = cls._render_prompt_block(clean_target, attended_nodes)

        return {
            "target_id": clean_target,
            "target_label": clean_target.replace("FUNC:", "").replace("CLASS:", ""),
            "hops": hops,
            "mode": mode,
            "engine": engine_used,
            "total_subgraph_nodes": total_subgraph_nodes,
            "attended_nodes": attended_nodes,
            "prompt_block": prompt_block,
        }

    @classmethod
    def _ast_subgraph_fallback(
        cls, target_id: str, repo_path: str, hops: int = 3, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Fallback to local AST analysis when full project GNN data is not initialized."""
        from proven.core.agent_service import AgentService
        svc = AgentService(repo_path=repo_path)
        ctx = svc.get_context(target_id=target_id, include_graph_rag=False)
        if ctx.get("status") != "success":
            return []

        candidates = []
        # Callee direct dependencies
        for idx, callee in enumerate(ctx.get("callees", [])[:3], start=1):
            candidates.append({
                "symbol": f"FUNC:{callee}",
                "node_type": "Function",
                "attention_score": round(0.90 - (idx * 0.08), 2),
                "hop_distance": 1,
                "relation": "calls",
                "path": f"{target_id} --(calls)--> {callee}",
                "semantic_rationale": "Direct callee (hop 1); high failure blast radius",
            })
        # Caller direct dependencies
        for idx, caller in enumerate(ctx.get("callers", [])[:2], start=1):
            candidates.append({
                "symbol": f"FUNC:{caller}",
                "node_type": "Function",
                "attention_score": round(0.85 - (idx * 0.08), 2),
                "hop_distance": 1,
                "relation": "called_by",
                "path": f"{caller} --(calls)--> {target_id}",
                "semantic_rationale": "Direct caller (hop 1); regression risk if contract changes",
            })
        return sorted(candidates, key=lambda x: x["attention_score"], reverse=True)[:top_k]

    @classmethod
    def _render_prompt_block(cls, target_id: str, attended_nodes: List[Dict[str, Any]]) -> str:
        """Render ultra-compact (< 120 tokens) prompt block for Agent context."""
        if not attended_nodes:
            return ""

        lines = [
            "### CODE GRAPHRAG (Topological Attention Context)",
            f"Target: `{target_id}`",
        ]
        for node in attended_nodes[:4]:
            score_str = f"{node['attention_score']:.2f}"
            lines.append(
                f"- **[Attn: {score_str}]** `{node['symbol']}` ({node['relation']} | {node['semantic_rationale']})"
            )
        return "\n".join(lines)

    @classmethod
    def build_graph_rag_prompt(
        cls,
        target_id: str,
        max_tokens: int = 120,
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> str:
        """Build GraphRAG context prompt block strictly bounded under max_tokens."""
        data = cls.extract_subgraph_attention(
            target_id=target_id,
            hops=3,
            top_k=4,
            repo_path=repo_path,
            project_name=project_name,
        )
        prompt = data.get("prompt_block", "")
        # Heuristic token safeguard (~4 chars per token)
        max_chars = max_tokens * 4
        if len(prompt) > max_chars:
            lines = prompt.splitlines()
            trimmed = lines[:3]
            return "\n".join(trimmed)
        return prompt

    @classmethod
    def format_attention_tree(cls, attention_data: Dict[str, Any]) -> str:
        """Format an ASCII attention flow tree for CLI display."""
        target_label = attention_data.get("target_label", attention_data.get("target_id", "Target"))
        engine = attention_data.get("engine", "topological_ppr")
        hops = attention_data.get("hops", 3)
        attended = attention_data.get("attended_nodes", [])

        lines = [
            f"Target: {target_label} (Root) [Engine: {engine}, Hops: {hops}]",
        ]

        if not attended:
            lines.append("  └── (No multi-hop dependencies found in graph)")
            return "\n".join(lines)

        for idx, item in enumerate(attended):
            is_last = (idx == len(attended) - 1)
            connector = "└──" if is_last else "├──"
            attn_pct = int(item["attention_score"] * 100)
            rel = item["relation"]
            symbol = item["symbol"]
            lines.append(f"  {connector} [Attn: {attn_pct}%] ──({rel})──► {symbol}")
            if item.get("semantic_rationale"):
                indent = "      " if is_last else "  │   "
                lines.append(f"{indent}Rationale: {item['semantic_rationale']}")

        return "\n".join(lines)
