#!/usr/bin/env python3
"""Standalone script for Coding Agents: Scan Git diff/PR impact and output missing runtime coverage gaps as JSON."""

import argparse
import json
import sys
import os

# Ensure package root and skill root are in sys.path
_script_dir = os.path.dirname(os.path.abspath(__file__))
_skill_root = os.path.abspath(os.path.join(_script_dir, ".."))
_repo_root = os.path.abspath(os.path.join(_script_dir, "..", ".."))
for p in (_skill_root, _repo_root):
    if p not in sys.path:
        sys.path.insert(0, p)

from proven.core.agent_service import AgentService

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ScanImpactOutput",
    "description": "Output schema of scan_impact.py for changed code and coverage gap detection",
    "type": "object",
    "properties": {
        "changed_count": {"type": "integer", "description": "Total count of changed functions in the diff"},
        "contract_diff_count": {"type": "integer", "description": "Count of functions with modified interfaces/contracts"},
        "missing_count": {"type": "integer", "description": "Count of changed functions lacking runtime test proof"},
        "language": {"type": "string", "description": "Detected primary programming language"},
        "missing_coverage": {
            "type": "array",
            "description": "List of functions requiring test coverage",
            "items": {
                "type": "object",
                "properties": {
                    "target_id": {"type": "string", "description": "Unique identifier, e.g. FUNC:process_order"},
                    "file": {"type": "string", "description": "Source file path"},
                    "risk": {"type": "number", "description": "Calculated risk score between 0.0 and 1.0"}
                },
                "required": ["target_id", "file"]
            }
        }
    },
    "required": ["changed_count", "missing_count", "missing_coverage"]
}


def main():
    parser = argparse.ArgumentParser(description="Scan PR impact and find uncovered functions")
    parser.add_argument("--project", default=None, help="Project name (defaults to repository folder name)")
    parser.add_argument("--path", default=".", help="Repository path")
    parser.add_argument("--base", default="main", help="Base git ref")
    parser.add_argument("--head", default="HEAD", help="Head git ref")
    parser.add_argument("--source", default="auto", choices=["auto", "git", "filesystem", "full-scan"], help="Diff source")
    parser.add_argument("--lang", default=None, help="Language override (python, typescript, go, etc.)")
    parser.add_argument("--cache-dir", default=None, help="Custom cache directory")
    parser.add_argument("--fan-out", action="store_true", help="Generate parallel Sub-Agent worker tasks")
    parser.add_argument("--schema", action="store_true", help="Print JSON Schema for output and exit")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        sys.exit(0)

    try:
        svc = AgentService(project=args.project, repo_path=args.path, language=args.lang, cache_dir=args.cache_dir)
        if args.fan_out:
            result = svc.generate_fanout_tasks(base_ref=args.base, head_ref=args.head, lang=args.lang)
        else:
            result = svc.scan(base=args.base, head=args.head, change_source=args.source, lang=args.lang)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        err = {"status": "error", "message": str(e)}
        print(json.dumps(err, indent=2, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
