#!/usr/bin/env python3
"""Standalone script for Coding Agents: Commit a synthesized Axiom into graph memory as JSON."""

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
    "title": "CommitAxiomOutput",
    "description": "Output schema of commit_axiom.py for committing a synthesized axiom",
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["success", "error"]},
        "axiom_id": {"type": "string"},
        "module": {"type": "string"},
        "rule": {"type": "string"},
        "consolidated_lessons_count": {"type": "integer"},
        "message": {"type": "string"}
    },
    "required": ["status", "axiom_id", "rule"]
}


def main():
    parser = argparse.ArgumentParser(description="Commit an agent-synthesized axiom into the graph memory")
    parser.add_argument("--cluster-id", default=None, help="Unique cluster ID from consolidate_memory.py")
    parser.add_argument("--module", default=None, help="Module namespace for the axiom (e.g. auth, payments)")
    parser.add_argument("--rule", default=None, help="Imperative distilled axiom rule (< 15 words)")
    parser.add_argument("--lesson-ids", default=None, help="Comma-separated list of child LESSON node IDs")
    parser.add_argument("--project", default=None, help="Project name")
    parser.add_argument("--path", default=".", help="Repository path")
    parser.add_argument("--schema", action="store_true", help="Print JSON Schema for output and exit")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        sys.exit(0)

    if not args.cluster_id or not args.module or not args.rule or not args.lesson_ids:
        parser.error("--cluster-id, --module, --rule, and --lesson-ids are all required")

    lesson_ids = [lid.strip() for lid in args.lesson_ids.split(",") if lid.strip()]
    if not lesson_ids:
        parser.error("--lesson-ids must contain at least one valid node ID")

    try:
        res = GraphMemoryManager.commit_synthesized_axiom(
            cluster_id=args.cluster_id,
            module=args.module,
            rule=args.rule,
            lesson_ids=lesson_ids,
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
