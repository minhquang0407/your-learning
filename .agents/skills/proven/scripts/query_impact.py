#!/usr/bin/env python3
"""Standalone script for Coding Agents: Query direct dependents and latent HGT blast radius for a symbol."""

import argparse
import json
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_skill_root = os.path.abspath(os.path.join(_script_dir, ".."))
_repo_root = os.path.abspath(os.path.join(_script_dir, "..", ".."))
for p in (_skill_root, _repo_root):
    if p not in sys.path:
        sys.path.insert(0, p)

from proven.core.agent_service import AgentService

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "QueryImpactOutput",
    "description": "Output schema of query_impact.py for impact and blast radius predictions",
    "type": "object",
    "properties": {
        "target_symbol": {"type": "string"},
        "mode": {"type": "string"},
        "threshold": {"type": "number"},
        "predictions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "node": {"type": "string"},
                    "score": {"type": "number"},
                    "relation": {"type": "string"}
                }
            }
        }
    },
    "required": ["target_symbol", "predictions"]
}


def main():
    parser = argparse.ArgumentParser(description="Query blast radius and latent GNN impact for a target symbol")
    parser.add_argument("--target", default=None, help="Target symbol ID (e.g. FUNC:module.function)")
    parser.add_argument("--mode", default="hybrid", choices=["hybrid", "graph", "gnn"], help="Impact analysis mode")
    parser.add_argument("--threshold", type=float, default=0.1, help="Score threshold")
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
        result = svc.predict_impact(target_symbol=args.target, mode=args.mode, threshold=args.threshold)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        err = {"status": "error", "message": str(e)}
        print(json.dumps(err, indent=2, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
