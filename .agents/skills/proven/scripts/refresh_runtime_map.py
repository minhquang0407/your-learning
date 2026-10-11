#!/usr/bin/env python3
"""Standalone script for Coding Agents: Refresh runtime test coverage graph across repository."""

import argparse
import json
import sys
import os

_script_dir = os.path.dirname(os.path.abspath(__file__))
_skill_root = os.path.abspath(os.path.join(_script_dir, ".."))
_repo_root = os.path.abspath(os.path.join(_script_dir, "..", ".."))
for p in (_skill_root, _repo_root):
    if p not in sys.path:
        sys.path.insert(0, p)

from proven.core.agent_service import AgentService

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "RefreshRuntimeMapOutput",
    "description": "Output schema of refresh_runtime_map.py for runtime coverage graph refresh",
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "project": {"type": "string"},
        "target_used": {"type": "string"},
        "mode_used": {"type": "string"},
        "passed_tests": {"type": "integer"},
        "failed_tests": {"type": "integer"},
        "runtime_edges_count": {"type": "integer"},
        "persisted": {"type": "boolean"},
        "warnings": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["status", "passed_tests"]
}


def main():
    parser = argparse.ArgumentParser(description="Refresh runtime coverage map across tests")
    parser.add_argument("--tests", default=None, help="Target test file or folder authored by agent (e.g. tests/test_foo.py)")
    parser.add_argument("--pytest-args", default=None, help="Alias for --tests or additional pytest options")
    parser.add_argument("--project", default=None, help="Project name")
    parser.add_argument("--path", default=".", help="Repository path")
    parser.add_argument("--schema", action="store_true", help="Print JSON Schema for output and exit")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        sys.exit(0)

    try:
        svc = AgentService(project=args.project, repo_path=args.path)
        target = args.tests or args.pytest_args
        result = svc.refresh_runtime(tests=target)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        err = {"status": "error", "message": str(e)}
        print(json.dumps(err, indent=2, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
