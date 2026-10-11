#!/usr/bin/env python3
"""Standalone script for Coding Agents: Verify runtime execution proof against target function.

Supports:
- Track 1 (Native Python): via --test tests/test_*.py (runs pytest + coverage.py)
- Track 2 (Universal Engine): via --lcov <path> or --test-cmd "<custom test command>"
"""

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
    "title": "VerifyRuntimeProofOutput",
    "description": "Output schema of verify_runtime_proof.py for runtime proof and mutation verification",
    "type": "object",
    "properties": {
        "target_id": {"type": "string"},
        "proof_status": {"type": "string", "enum": ["pass", "fail", "inconclusive"]},
        "covered_fraction": {"type": "number"},
        "covered_lines": {"type": "array", "items": {"type": "integer"}},
        "total_lines": {"type": "integer"},
        "message": {"type": "string"},
        "mutation_results": {
            "type": "object",
            "properties": {
                "killed": {"type": "integer"},
                "survived": {"type": "integer"},
                "total": {"type": "integer"},
                "mutation_score": {"type": "number"}
            }
        },
        "self_healing": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "diagnosis_type": {"type": "string"},
                "explanation": {"type": "string"},
                "actionable_suggestion": {"type": "string"}
            }
        }
    },
    "required": ["target_id", "proof_status", "covered_fraction"]
}


def main():
    parser = argparse.ArgumentParser(description="Verify runtime proof of a written test for a target function")
    parser.add_argument("--target", default=None, help="Target ID (e.g. FUNC:my_func)")
    parser.add_argument("--test", default=None, help="Test target file or function (e.g. tests/test_foo.py)")
    parser.add_argument("--file", default=None, help="Source file path if known")
    parser.add_argument("--pytest-args", default=None, help="Additional pytest arguments (Track 1)")
    parser.add_argument("--lcov", default=None, help="Path to lcov.info or coverage.out (Track 2 Universal)")
    parser.add_argument("--test-cmd", default=None, help="Custom test execution command (e.g. npm test -- --coverage)")
    parser.add_argument("--lang", default=None, help="Language override (python, typescript, go, etc.)")
    parser.add_argument("--mutation-check", action="store_true", help="Run MicroMutationGate to prove assertion strength (Titanium Proof)")
    parser.add_argument("--max-mutants", type=int, default=2, help="Maximum AST mutants to test (default 2)")
    parser.add_argument("--project", default=None, help="Project name")
    parser.add_argument("--path", default=".", help="Repository path")
    parser.add_argument("--cache-dir", default=None, help="Custom cache directory")
    parser.add_argument("--schema", action="store_true", help="Print JSON Schema for output and exit")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        sys.exit(0)

    if not args.target:
        parser.error("--target is required unless --schema is specified")

    try:
        svc = AgentService(project=args.project, repo_path=args.path, language=args.lang, cache_dir=args.cache_dir)
        result = svc.verify_proof(
            target_id=args.target,
            test_target=args.test,
            pytest_args=args.pytest_args,
            lcov_path=args.lcov,
            test_cmd=args.test_cmd,
            lang=args.lang,
            mutation_check=args.mutation_check,
            max_mutants=args.max_mutants,
            source_file=args.file,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("proof_status") != "pass":
            sys.exit(2)
    except Exception as e:
        err = {"status": "error", "message": str(e), "proof_status": "fail"}
        print(json.dumps(err, indent=2, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
