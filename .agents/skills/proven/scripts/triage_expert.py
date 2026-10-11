#!/usr/bin/env python3
"""Standalone script for Coding Agents: Recommend best-suited engineers and related files for a bug/PR."""

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
    "title": "TriageExpertOutput",
    "description": "Output schema of triage_expert.py for developer and file recommendations",
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "developers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "developer": {"type": "string"},
                    "score": {"type": "number"}
                }
            }
        },
        "related_files": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["query", "developers"]
}


def main():
    parser = argparse.ArgumentParser(description="Triage bug description and recommend expert reviewers")
    parser.add_argument("--query", default=None, help="Bug report description or PR title/changes")
    parser.add_argument("--max-devs", type=int, default=3, help="Maximum number of developers to recommend")
    parser.add_argument("--max-files", type=int, default=5, help="Maximum number of related files to return")
    parser.add_argument("--project", default=None, help="Project name")
    parser.add_argument("--path", default=".", help="Repository path")
    parser.add_argument("--schema", action="store_true", help="Print JSON Schema for output and exit")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        sys.exit(0)

    if not args.query:
        parser.error("--query is required unless --schema is specified")

    try:
        svc = AgentService(project=args.project, repo_path=args.path)
        result = svc.triage_bug(query=args.query, max_devs=args.max_devs, max_files=args.max_files)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        err = {"status": "error", "message": str(e)}
        print(json.dumps(err, indent=2, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
