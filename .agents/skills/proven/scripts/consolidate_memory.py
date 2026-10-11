#!/usr/bin/env python3
"""Standalone script for Coding Agents: Run Sleep Consolidation on graph-pinned memory as JSON."""

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

from proven.core.memory_manager import GraphMemoryManager

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ConsolidateMemoryOutput",
    "description": "Output schema of consolidate_memory.py for sleep consolidation",
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["NEEDS_SYNTHESIS", "threshold_not_met", "noop", "success", "error"]},
        "message": {"type": "string"},
        "count": {"type": "integer"},
        "threshold": {"type": "integer"},
        "clusters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cluster_id": {"type": "string"},
                    "module": {"type": "string"},
                    "category": {"type": "string"},
                    "lesson_ids": {"type": "array", "items": {"type": "string"}},
                    "lessons": {"type": "array", "items": {"type": "string"}},
                    "traps": {"type": "array", "items": {"type": "string"}},
                    "target_ids": {"type": "array", "items": {"type": "string"}},
                    "prompt_instruction": {"type": "string"}
                }
            }
        },
        "total_axioms": {"type": "integer"},
        "axioms_file": {"type": "string"},
        "modules": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["status", "message"]
}


def main():
    parser = argparse.ArgumentParser(description="Consolidate pinned graph lessons into repo-wide axioms")
    parser.add_argument("--project", default=None, help="Project name")
    parser.add_argument("--path", default=".", help="Repository path")
    parser.add_argument("--threshold", type=int, default=10, help="Minimum unconsolidated lessons required to trigger sleep (default: 10)")
    parser.add_argument("--force", action="store_true", help="Bypass threshold gate and consolidate immediately")
    parser.add_argument("--check-only", action="store_true", help="Only check if sleep threshold is met without modifying memory")
    parser.add_argument("--auto-fallback", action="store_true", help="Automatically consolidate using deterministic rules without agent synthesis")
    parser.add_argument("--schema", action="store_true", help="Print JSON Schema for output and exit")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        sys.exit(0)

    try:
        if args.check_only:
            res = GraphMemoryManager.check_sleep_trigger(
                threshold=args.threshold, repo_path=args.path, project_name=args.project
            )
            print(json.dumps(res, indent=2, ensure_ascii=False))
            sys.exit(0)

        if args.auto_fallback:
            res = GraphMemoryManager.consolidate_axioms(
                repo_path=args.path,
                project_name=args.project,
                threshold=args.threshold,
                force=args.force,
            )
            print(json.dumps(res, indent=2, ensure_ascii=False))
            sys.exit(0)

        res = GraphMemoryManager.cluster_unconsolidated_lessons(
            threshold=args.threshold,
            force=args.force,
            repo_path=args.path,
            project_name=args.project,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        sys.exit(0)
    except Exception as e:
        err = {"status": "error", "message": str(e)}
        print(json.dumps(err, indent=2, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
