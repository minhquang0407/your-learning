#!/usr/bin/env python3
"""Standalone script for Coding Agents: Run Proven Empirical AI Benchmark as JSON."""

import argparse
import json
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_skill_root = os.path.abspath(os.path.join(_script_dir, ".."))
_skills_dir = os.path.abspath(os.path.join(_script_dir, "..", ".."))
_repo_root = os.path.abspath(os.path.join(_script_dir, "..", "..", ".."))
for p in (_script_dir, _skill_root, _skills_dir, _repo_root, os.getcwd()):
    if p not in sys.path:
        sys.path.insert(0, p)

from proven.core.benchmark import BenchmarkEvaluator, BenchmarkReporter, EvolutionSimulator

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "BenchmarkOutput",
    "description": "Output schema of run_benchmark.py for empirical evaluation",
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "targets_count": {"type": "integer"},
        "baseline": {"type": "object"},
        "proven_pro": {"type": "object"},
        "deltas": {"type": "object"},
        "targets": {"type": "array"}
    },
    "required": ["targets_count", "baseline", "proven_pro", "deltas"]
}


def main():
    parser = argparse.ArgumentParser(description="Run Proven Empirical Benchmark")
    parser.add_argument("--project", default=None, help="Project name")
    parser.add_argument("--path", default=".", help="Repository path")
    parser.add_argument("--evolution", action="store_true", help="Run multi-turn incremental evolution simulation")
    parser.add_argument("--rounds", type=int, default=4, help="Rounds for evolution simulation (default: 4)")
    parser.add_argument("--report-file", default=None, help="Export Markdown report to specified path")
    parser.add_argument("--visualize", action="store_true", help="Print ASCII summary table to stderr")
    parser.add_argument("--schema", action="store_true", help="Print JSON Schema for output and exit")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(SCHEMA, indent=2))
        return

    if args.evolution:
        sim = EvolutionSimulator(repo_path=args.path, project_name=args.project)
        result = sim.run_evolution_simulation(rounds=args.rounds)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    evaluator = BenchmarkEvaluator(repo_path=args.path, project_name=args.project)
    summary = evaluator.evaluate_suite()

    if args.report_file:
        BenchmarkReporter.render_markdown_report(summary, output_path=args.report_file)

    if args.visualize:
        table_text = BenchmarkReporter.render_cli_summary(summary)
        sys.stderr.write(table_text + "\n")

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
