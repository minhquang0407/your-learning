#!/usr/bin/env python3
"""Standalone script for Coding Agents: Extract and explain multi-hop GNN subgraph attention as JSON."""

import argparse
import json
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_skill_root = os.path.abspath(os.path.join(_script_dir, ".."))
_repo_root = os.path.abspath(os.path.join(_script_dir, "..", "..", ".."))
for p in (_repo_root, _skill_root):
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

from proven.core.agent_service import AgentService
from proven.core.graph_rag import CodeGraphRAG

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ExplainAttentionOutput",
    "description": "Output schema of explain_attention.py for multi-hop GNN subgraph attention",
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["success", "error"]},
        "target_id": {"type": "string"},
        "target_label": {"type": "string"},
        "hops": {"type": "integer"},
        "mode": {"type": "string"},
        "engine": {"type": "string"},
        "total_subgraph_nodes": {"type": "integer"},
        "attended_nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "node_type": {"type": "string"},
                    "attention_score": {"type": "number"},
                    "hop_distance": {"type": "integer"},
                    "relation": {"type": "string"},
                    "path": {"type": "string"},
                    "semantic_rationale": {"type": "string"}
                },
                "required": ["symbol", "attention_score", "hop_distance", "relation"]
            }
        },
        "ascii_tree": {"type": "string"},
        "prompt_block": {"type": "string"}
    },
    "required": ["status", "target_id", "attended_nodes"]
}


def main():
    parser = argparse.ArgumentParser(description="Explain multi-hop GNN/topological attention for a target symbol")
    parser.add_argument("--target", default=None, help="Target symbol ID (e.g. FUNC:module.function)")
    parser.add_argument("--hops", type=int, default=3, help="Number of message-passing hops (default: 3)")
    parser.add_argument("--top-k", type=int, default=5, help="Number of top attended nodes to retrieve (default: 5)")
    parser.add_argument("--mode", choices=["hybrid", "gnn", "topological"], default="hybrid", help="Attention extraction mode")
    parser.add_argument("--visualize", action="store_true", help="Print ASCII attention tree to stdout")
    parser.add_argument("--project", default=None, help="Project name")
    parser.add_argument("--path", default=".", help="Repository path")
    parser.add_argument("--schema", action="store_true", help="Print JSON Schema for output and exit")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        sys.exit(0)

    if not args.target:
        parser.error("--target is required unless --schema is specified")

    try:
        svc = AgentService(project=args.project, repo_path=args.path)
        data = svc.explain_attention(
            target_symbol=args.target,
            hops=args.hops,
            top_k=args.top_k,
            mode=args.mode,
        )
        data["status"] = "success"

        if args.visualize:
            print(data.get("ascii_tree", ""))
            print("\n" + data.get("prompt_block", ""))
            sys.exit(0)

        print(json.dumps(data, indent=2, ensure_ascii=False))
        sys.exit(0)
    except Exception as e:
        err = {"status": "error", "message": str(e), "target_id": args.target}
        print(json.dumps(err, indent=2, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
