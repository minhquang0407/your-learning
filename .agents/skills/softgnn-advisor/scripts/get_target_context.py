#!/usr/bin/env python3
"""Standalone script for Coding Agents: Extract surgical AST context for a target function as JSON."""

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

from softgnn_advisor.core.agent_service import AgentService

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GetTargetContextOutput",
    "description": "Output schema of get_target_context.py for function AST context",
    "type": "object",
    "properties": {
        "target_id": {"type": "string", "description": "Target identifier"},
        "file": {"type": "string", "description": "Source file path"},
        "line_start": {"type": "integer", "description": "Starting line number"},
        "line_end": {"type": "integer", "description": "Ending line number"},
        "source_code": {"type": "string", "description": "Extracted source code of the function"},
        "callers": {"type": "array", "items": {"type": "string"}},
        "callees": {"type": "array", "items": {"type": "string"}},
        "test_suite": {"type": "string", "description": "Suggested test framework and runner"}
    },
    "required": ["target_id", "file", "source_code"]
}


def main():
    parser = argparse.ArgumentParser(description="Extract surgical AST context for a target function or file")
    parser.add_argument("--target", default=None, help="Target ID (e.g. FUNC:my_func)")
    parser.add_argument("--file", default=None, help="Source file path if known")
    parser.add_argument("--project", default=None, help="Project name")
    parser.add_argument("--path", default=".", help="Repository path")
    parser.add_argument("--cache-dir", default=None, help="Custom cache directory")
    parser.add_argument("--schema", action="store_true", help="Print JSON Schema for output and exit")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        sys.exit(0)

    if not args.target and not args.file:
        parser.error("At least one of --target or --file is required unless --schema is specified")

    try:
        svc = AgentService(project=args.project, repo_path=args.path, cache_dir=args.cache_dir)
        result = svc.get_context(target_id=args.target, source_file=args.file)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        err = {"status": "error", "message": str(e)}
        print(json.dumps(err, indent=2, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
