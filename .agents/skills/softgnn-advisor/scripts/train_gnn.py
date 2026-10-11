#!/usr/bin/env python3
"""Standalone script for Coding Agents: Trigger offline HGT Graph AI training for the codebase."""

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

from softgnn_advisor.core.agent_service import AgentService

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "TrainGnnOutput",
    "description": "Output schema of train_gnn.py for offline HGT GNN model training",
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "epochs": {"type": "integer"},
        "best_val_auc": {"type": "number"},
        "test_auc": {"type": "number"},
        "model_path": {"type": "string"}
    },
    "required": ["status"]
}


def main():
    parser = argparse.ArgumentParser(description="Train HGT Graph AI model for codebase link prediction")
    parser.add_argument("--project", default=None, help="Project name")
    parser.add_argument("--path", default=".", help="Repository path")
    parser.add_argument("--schema", action="store_true", help="Print JSON Schema for output and exit")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        sys.exit(0)

    try:
        svc = AgentService(project=args.project, repo_path=args.path)
        result = svc.train_gnn()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        err = {"status": "error", "message": str(e)}
        print(json.dumps(err, indent=2, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
