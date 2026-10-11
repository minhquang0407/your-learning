import ast
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from softgnn_advisor.config.settings import get_project_paths
from softgnn_advisor.core.change_provider import (
    build_filesystem_snapshot,
    save_filesystem_snapshot,
    snapshot_path_for_project,
)
from softgnn_advisor.core.metadata_utils import load_metadata
from softgnn_advisor.core.pr_scanner import PRScanner
from softgnn_advisor.infrastructure.pipelines.language_router import detect_project_language
from softgnn_advisor.infrastructure.pipelines.runtime_coverage_mapper import RuntimeCoverageMapper
from softgnn_advisor.infrastructure.pipelines.universal_ast_parser import UniversalASTParser
from softgnn_advisor.infrastructure.pipelines.universal_coverage_mapper import UniversalCoverageMapper
from softgnn_advisor.core.branch_diagnoser import BranchDiagnoser
from softgnn_advisor.core.mutation_gate import MicroMutationGate
from softgnn_advisor.scripts.etl_run import run_etl_pipeline


class AgentService:
    """Core service providing structured graph intelligence and runtime proof gates for Coding Agents.

    Implements a Dual-Track Architecture:
    - Track 1 (Native Python): 100% existing native AST & pytest runtime trace pipeline.
    - Track 2 (Universal Engine): Tree-sitter AST & LCOV/Coverprofile pipeline for all other languages.
    """

    def __init__(self, project=None, repo_path=None, language=None):
        self.repo_path = os.path.abspath(repo_path or os.getcwd())
        self.project = project or self._infer_project_name(self.repo_path)
        self.paths = get_project_paths(self.project)
        self.language = language or detect_project_language(self.repo_path)

    @staticmethod
    def _infer_project_name(repo_path):
        normalized = os.path.abspath(repo_path).rstrip('\\/')
        base = os.path.basename(normalized)
        return base or 'default'

    def ensure_initialized(self, auto_etl=True):
        """Ensure graph data exists for this project (Track 1); if not and auto_etl is True, run ETL pipeline."""
        if self.language != 'python':
            return True

        nodes_path = self.paths['NODES_DATA_PATH']
        if os.path.exists(nodes_path) and os.path.getsize(nodes_path) > 0:
            return True
        if not auto_etl:
            return False

        import contextlib
        with contextlib.redirect_stdout(sys.stderr):
            run_etl_pipeline(self.repo_path, self.project)
            snap = build_filesystem_snapshot(self.repo_path)
            save_filesystem_snapshot(snapshot_path_for_project(self.project), snap)
        return True

    def scan(self, base='main', head='HEAD', change_source='auto', lang=None):
        """Scan PR/diff impact and identify uncovered changed functions.

        Routes to Track 1 for Python, and Track 2 (Universal) for other languages.
        """
        active_lang = lang or self.language

        # --- Track 1: Native Python Track ---
        if active_lang == 'python':
            self.ensure_initialized()
            scanner = PRScanner(self.project, repo_path=self.repo_path)
            scan_res = scanner.scan(
                base=base,
                head=head,
                mode='deterministic',
                max_impact=20,
                suggest_tests=True,
                change_source=change_source,
            )

            changed_nodes = [
                {
                    'id': node.full_id,
                    'label': node.label,
                    'type': node.node_type,
                    'file': node.source_file,
                }
                for node in scan_res.changed_nodes
            ]

            contract_changes = [
                {
                    'function_id': cc.function_id,
                    'signature_changed': cc.signature_changed,
                    'return_pattern_changed': cc.return_pattern_changed,
                    'behavior_changed': cc.behavior_changed,
                    'source_only_changed': cc.source_only_changed,
                    'summary': cc.summary,
                }
                for cc in scan_res.contract_changes
            ]

            hotspots = [
                {
                    'label': h.label,
                    'type': h.node_type,
                    'risk_score': round(float(h.risk_score), 3),
                    'risk_level': h.risk_level,
                    'evidence': h.evidence,
                }
                for h in scan_res.impact_hotspots
            ]

            suggestions_map = {cover: s for s in scan_res.suggested_tests for cover in s.covers}
            missing_coverage = []
            for gap in scan_res.missing_coverage:
                sug = suggestions_map.get(gap.target_id)
                suggested_file = sug.suggested_file if sug else self._suggest_test_file(gap.target_id)
                missing_coverage.append({
                    'target_id': gap.target_id,
                    'reason': gap.reason,
                    'suggested_action': gap.suggested_action,
                    'suggested_test_file': suggested_file,
                })

            return {
                'status': 'success',
                'project': self.project,
                'repo_path': self.repo_path,
                'track': 'native_python',
                'language': 'python',
                'change_source': scan_res.change_source,
                'changed_files': [f.path if hasattr(f, 'path') else str(f) for f in scan_res.changed_files],
                'changed_nodes': changed_nodes,
                'contract_changes': contract_changes,
                'impact_hotspots': hotspots,
                'missing_coverage': missing_coverage,
                'warnings': scan_res.warnings,
            }

        # --- Track 2: Universal Engine Track (TS/JS, Go, Rust, Java, etc.) ---
        return self._universal_scan(base, head, active_lang)

    def _universal_scan(self, base, head, lang):
        """Universal diff scan using git and UniversalASTParser."""
        changed_files = self._get_git_changed_files(base, head)
        parser = UniversalASTParser(self.repo_path)
        changed_nodes = []
        missing_coverage = []

        for rel_file in changed_files:
            _, ext = os.path.splitext(rel_file.lower())
            if ext in UniversalASTParser.EXT_TO_LANG:
                abs_file = os.path.join(self.repo_path, rel_file)
                parsed_fns = parser.parse_file(abs_file)
                for fn in parsed_fns:
                    fn_id = fn['function_id']
                    changed_nodes.append({
                        'id': fn_id,
                        'label': fn['name'],
                        'type': 'Function',
                        'file': rel_file,
                    })
                    suggested_test = self._suggest_test_file(rel_file)
                    missing_coverage.append({
                        'target_id': fn_id,
                        'reason': 'Unverified runtime coverage in changed file',
                        'suggested_action': f'Write test in {suggested_test} and verify runtime proof',
                        'suggested_test_file': suggested_test,
                    })

        return {
            'status': 'success',
            'project': self.project,
            'repo_path': self.repo_path,
            'track': 'universal_engine',
            'language': lang,
            'change_source': 'git',
            'changed_files': changed_files,
            'changed_nodes': changed_nodes,
            'contract_changes': [],
            'impact_hotspots': [],
            'missing_coverage': missing_coverage,
            'warnings': [],
        }

    def _get_git_changed_files(self, base, head):
        try:
            cmd = ['git', 'diff', '--name-only', f'{base}...{head}']
            proc = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True, check=False)
            if proc.returncode == 0 and proc.stdout.strip():
                return [line.strip().replace('\\', '/') for line in proc.stdout.splitlines() if line.strip()]
            # Fallback to local unstaged/staged git diff
            cmd_fallback = ['git', 'diff', '--name-only', 'HEAD']
            proc2 = subprocess.run(cmd_fallback, cwd=self.repo_path, capture_output=True, text=True, check=False)
            if proc2.returncode == 0:
                return [line.strip().replace('\\', '/') for line in proc2.stdout.splitlines() if line.strip()]
        except Exception:
            pass
        return []

    def get_context(self, target_id, source_file=None, lang=None):
        """Extract surgical context for target function."""
        active_lang = lang or self.language
        resolved_file = source_file or self._resolve_source_file(target_id)

        if not resolved_file:
            return {
                'status': 'error',
                'target_id': target_id,
                'message': f"Could not resolve source file for target '{target_id}'. Please provide source_file parameter.",
            }

        abs_source_path = os.path.join(self.repo_path, resolved_file.replace('/', os.sep))
        if not os.path.exists(abs_source_path):
            return {
                'status': 'error',
                'target_id': target_id,
                'message': f"Source file does not exist: {abs_source_path}",
            }

        source_code = Path(abs_source_path).read_text(encoding='utf-8', errors='replace')
        suggested_test_file = self._suggest_test_file(resolved_file)
        abs_test_path = os.path.join(self.repo_path, suggested_test_file.replace('/', os.sep))
        existing_test_content = None
        if os.path.exists(abs_test_path):
            existing_test_content = Path(abs_test_path).read_text(encoding='utf-8', errors='replace')

        # --- Track 1: Native Python AST ---
        if active_lang == 'python' and resolved_file.endswith('.py'):
            self.ensure_initialized()
            ast_info = self._parse_ast_context(source_code, target_id, resolved_file)
            callers, callees = self._query_graph_relations(target_id)
            return {
                'status': 'success',
                'track': 'native_python',
                'target_id': target_id,
                'source_file': resolved_file.replace('\\', '/'),
                'module_path': self._module_path(resolved_file),
                'signature': ast_info.get('signature', ''),
                'docstring': ast_info.get('docstring', ''),
                'source_code': ast_info.get('source', ''),
                'imports': ast_info.get('imports', []),
                'callers': callers,
                'callees': callees,
                'suggested_test_file': suggested_test_file,
                'existing_test_file_exists': bool(existing_test_content),
                'existing_test_preview': existing_test_content[:2000] if existing_test_content else None,
            }

        # --- Track 2: Universal AST Parser ---
        parser = UniversalASTParser(self.repo_path)
        parsed_fns = parser.parse_file(abs_source_path)
        matched_fn = None
        for fn in parsed_fns:
            if fn['function_id'] == target_id or fn['name'] == target_id.replace('FUNC:', ''):
                matched_fn = fn
                break

        target_source = matched_fn['source'] if matched_fn else source_code
        target_sig = matched_fn['signature'] if matched_fn else target_id

        return {
            'status': 'success',
            'track': 'universal_engine',
            'target_id': target_id,
            'language': active_lang,
            'source_file': resolved_file.replace('\\', '/'),
            'signature': target_sig,
            'source_code': target_source,
            'suggested_test_file': suggested_test_file,
            'existing_test_file_exists': bool(existing_test_content),
            'existing_test_preview': existing_test_content[:2000] if existing_test_content else None,
        }

    def verify_proof(
        self,
        target_id: str,
        test_target: str = None,
        pytest_args: str = None,
        lcov_path: str = None,
        test_cmd: str = None,
        lang: str = None,
        mutation_check: bool = False,
        max_mutants: int = 2,
    ) -> dict:
        """Verify runtime execution proof for a written test against target_id.

        If lcov_path or test_cmd is provided, or language is not Python, routes to Track 2 (Universal Engine).
        Otherwise routes to Track 1 (Native Python pytest coverage).
        If mutation_check is True, additionally runs MicroMutationGate to prove assertion strength (Titanium Proof).
        """
        active_lang = lang or self.language

        # --- Track 2: Universal Engine (LCOV / Coverprofile / Custom Command) ---
        if lcov_path or test_cmd or active_lang != 'python':
            return self._universal_verify_proof(target_id, test_target, lcov_path, test_cmd)

        # --- Track 1: Native Python Pipeline ---
        self.ensure_initialized()
        if not test_target:
            return {
                'status': 'error',
                'proof_status': 'fail',
                'target_id': target_id,
                'message': "test_target is required for native Python verification (e.g. tests/test_foo.py).",
            }

        cmd = [sys.executable, '-m', 'pytest', test_target]
        if pytest_args:
            cmd.extend(pytest_args.split())

        proc = subprocess.run(
            cmd,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
        pytest_passed = (proc.returncode == 0)
        pytest_output = (proc.stdout + '\n' + proc.stderr).strip()

        if not pytest_passed:
            return {
                'status': 'error',
                'track': 'native_python',
                'proof_status': 'fail',
                'target_id': target_id,
                'test_target': test_target,
                'pytest_passed': False,
                'pytest_returncode': proc.returncode,
                'pytest_output': pytest_output,
                'message': f"Pytest failed with exit code {proc.returncode}. Tests must pass before runtime proof can be established.",
                'covered_fraction': 0.0,
                'covered_lines': [],
                'covered_line_count': 0,
                'function_line_count': 0,
                'matching_edges': [],
            }

        with tempfile.TemporaryDirectory(prefix="softgnn_cov_") as temp_cov_dir:
            mapper = RuntimeCoverageMapper(self.project, repo_path=self.repo_path, coverage_dir=temp_cov_dir)
            try:
                res = mapper.map_runtime_coverage(pytest_args=test_target, mode='per-test', persist=False)
                edges = res.runtime_edges
            except Exception as e:
                return {
                    'status': 'error',
                    'track': 'native_python',
                    'proof_status': 'fail',
                    'target_id': target_id,
                    'test_target': test_target,
                    'pytest_passed': True,
                    'pytest_returncode': 0,
                    'pytest_output': pytest_output,
                    'message': f"Coverage mapping failed: {e}",
                    'covered_fraction': 0.0,
                    'covered_lines': [],
                    'covered_line_count': 0,
                    'function_line_count': 0,
                    'matching_edges': [],
                    'self_healing': None,
                }

        matching = [e for e in edges if e.target_id == target_id]
        if matching:
            best = max(matching, key=lambda e: e.covered_fraction)
            short_test = best.test_id.split('::')[-1]
            msg = (
                f"Runtime proof CONFIRMED: {short_test} -> {target_id} "
                f"({best.covered_fraction:.0%} coverage, {best.covered_line_count}/{best.function_line_count} lines executed)."
            )
            diag = None
            if best.covered_fraction < 0.50:
                source_file = self._resolve_source_file(target_id)
                if source_file:
                    diag = BranchDiagnoser.diagnose_failure(
                        target_id=target_id,
                        source_file=source_file,
                        test_file=test_target,
                        covered_lines=best.covered_lines,
                        function_range=best.function_range,
                        repo_path=self.repo_path,
                    )
            mutation_res = None
            proof_grade = "SILVER"
            if mutation_check:
                s_file = self._resolve_source_file(target_id)
                if s_file:
                    mutation_res = MicroMutationGate.evaluate_mutations(
                        target_id=target_id,
                        source_file=s_file,
                        test_target=test_target,
                        repo_path=self.repo_path,
                        max_mutants=max_mutants,
                        pytest_args=pytest_args,
                    )
                    proof_grade = mutation_res.get("proof_grade", "SILVER")
                    if mutation_res.get("message"):
                        msg += f"\n{mutation_res['message']}"

            return {
                'status': 'success',
                'track': 'native_python',
                'proof_status': 'pass',
                'proof_grade': proof_grade,
                'target_id': target_id,
                'test_target': test_target,
                'pytest_passed': True,
                'pytest_returncode': 0,
                'pytest_output': pytest_output,
                'message': msg,
                'covered_fraction': round(best.covered_fraction, 4),
                'covered_lines': best.covered_lines,
                'covered_line_count': best.covered_line_count,
                'function_line_count': best.function_line_count,
                'matching_edges': [asdict(e) for e in matching],
                'self_healing': diag,
                'mutation_proof': mutation_res,
            }
        else:
            source_file = self._resolve_source_file(target_id)
            all_covered_files = {}
            for e in edges:
                all_covered_files.setdefault(e.source_file, set()).update(e.covered_lines)

            fn_ranges = mapper._collect_function_ranges()
            target_range = None
            if source_file and source_file in fn_ranges:
                for fn in fn_ranges[source_file]:
                    if fn.get('function_id') == target_id or fn.get('function_id') == f"FUNC:{target_id}":
                        target_range = [fn['start'], fn['end']]
                        break

            diag = BranchDiagnoser.diagnose_failure(
                target_id=target_id,
                source_file=source_file or "",
                test_file=test_target,
                covered_lines=[],
                function_range=target_range,
                all_covered_files=all_covered_files,
                repo_path=self.repo_path,
            )

            msg = (
                f"Runtime proof FAILED: Pytest passed, but test(s) in '{test_target}' did NOT execute target '{target_id}' "
                f"at runtime (0 lines executed). Check if the target function was mocked out or if test inputs did not trigger its execution path."
            )
            if diag and diag.get('explanation'):
                msg += f"\nSelf-Healing Diagnosis: {diag['explanation']}\nSuggestion: {diag['actionable_suggestion']}"

            return {
                'status': 'success',
                'track': 'native_python',
                'proof_status': 'fail',
                'target_id': target_id,
                'test_target': test_target,
                'pytest_passed': True,
                'pytest_returncode': 0,
                'pytest_output': pytest_output,
                'message': msg,
                'covered_fraction': 0.0,
                'covered_lines': [],
                'covered_line_count': 0,
                'function_line_count': 0,
                'matching_edges': [],
                'self_healing': diag,
            }

    def _universal_verify_proof(self, target_id, test_target, lcov_path, test_cmd):
        """Execute Universal Proof Gate against LCOV / Coverprofile."""
        test_output = ""
        # 1. Execute test command if provided
        if test_cmd:
            proc = subprocess.run(
                test_cmd,
                shell=True,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            test_output = proc.stdout + "\n" + proc.stderr
            if proc.returncode != 0:
                return {
                    'status': 'error',
                    'track': 'universal_engine',
                    'proof_status': 'fail',
                    'target_id': target_id,
                    'test_output': test_output,
                    'message': f"Test execution command failed with exit code {proc.returncode}.",
                    'covered_fraction': 0.0,
                    'covered_lines': [],
                    'self_healing': None,
                }

        # 2. Locate LCOV / Coverage file
        resolved_lcov = lcov_path
        if not resolved_lcov or not os.path.exists(resolved_lcov):
            candidates = [
                'coverage/lcov.info',
                'lcov.info',
                'coverage.out',
                'coverage/coverage.out',
                'coverage/coverage-final.json',
            ]
            for cand in candidates:
                cand_path = os.path.join(self.repo_path, cand)
                if os.path.exists(cand_path):
                    resolved_lcov = cand_path
                    break

        if not resolved_lcov or not os.path.exists(resolved_lcov):
            return {
                'status': 'error',
                'track': 'universal_engine',
                'proof_status': 'fail',
                'target_id': target_id,
                'test_output': test_output,
                'message': (
                    "Could not find coverage file (lcov.info or coverage.out). "
                    "Ensure tests run with coverage enabled (e.g. --coverage) or provide --lcov <path>."
                ),
                'covered_fraction': 0.0,
                'covered_lines': [],
                'self_healing': None,
            }

        # 3. Parse coverage and collect ranges
        cov_data = UniversalCoverageMapper.load_coverage(resolved_lcov)
        fn_ranges = UniversalASTParser(self.repo_path).collect_function_ranges()

        res = UniversalCoverageMapper.verify_proof(target_id, fn_ranges, cov_data)
        res['track'] = 'universal_engine'
        res['coverage_file'] = resolved_lcov
        if test_output:
            res['test_output'] = test_output

        # Self-healing diagnosis for Universal Engine
        if res.get('proof_status') == 'fail' or res.get('covered_fraction', 0) < 0.50:
            source_file = res.get('source_file') or self._resolve_source_file(target_id)
            if source_file:
                target_range = None
                for f, fns in fn_ranges.items():
                    for fn in fns:
                        if fn.get('function_id') == target_id or fn.get('name') == target_id.replace('FUNC:', ''):
                            target_range = [fn['start'], fn['end']]
                            break
                    if target_range:
                        break

                diag = BranchDiagnoser.diagnose_failure(
                    target_id=target_id,
                    source_file=source_file,
                    test_file=test_target,
                    covered_lines=res.get('covered_lines', []),
                    function_range=target_range,
                    repo_path=self.repo_path,
                )
                res['self_healing'] = diag
                if diag and diag.get('explanation'):
                    res['message'] += f"\nSelf-Healing Diagnosis: {diag['explanation']}\nSuggestion: {diag['actionable_suggestion']}"
        else:
            res['self_healing'] = None

        return res

    def refresh_runtime(self, tests=None, pytest_args=None, mode='auto'):
        """Re-run pytest coverage across repo and persist updated runtime edges.

        Priority:
        1. tests: explicitly provided by Agent (e.g. tests/test_billing.py)
        2. pytest_args: backwards compatibility argument
        3. auto-discovery: testpaths in config, tests/, test/, or .
        """
        self.ensure_initialized()
        target = tests or pytest_args
        if not target:
            target = self._discover_test_path()
        mapper = RuntimeCoverageMapper(self.project, repo_path=self.repo_path)
        res = mapper.map_runtime_coverage(pytest_args=target, mode=mode, persist=True)
        return {
            'status': 'success',
            'project': self.project,
            'target_used': target,
            'mode_used': res.mode_used,
            'passed_tests': res.passed_tests,
            'failed_tests': res.failed_tests,
            'runtime_edges_count': len(res.runtime_edges),
            'persisted': res.persisted,
            'warnings': res.warnings,
        }

    def _discover_test_path(self):
        """Auto-detect test folder or fallback to '.'"""
        pyproject = Path(self.repo_path) / 'pyproject.toml'
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding='utf-8')
                for line in content.splitlines():
                    if 'testpaths' in line and '=' in line:
                        parts = line.split('=', 1)[1].strip().strip('[]"')
                        first_path = parts.split(',')[0].strip(' "\'')
                        if (Path(self.repo_path) / first_path).exists():
                            return first_path
            except Exception:
                pass

        for folder in ['tests', 'test', 'src/tests', 'testing']:
            if (Path(self.repo_path) / folder).is_dir():
                return folder

        return '.'

    def generate_fanout_tasks(self, base="main", head="HEAD", lang="auto") -> dict:
        """Generate structured parallel worker tasks for Sub-Agent Swarms / skill-to-workflow."""
        scan_res = self.scan(base=base, head=head, lang=lang)
        missing = scan_res.get("missing_coverage", [])
        tasks = []
        for idx, item in enumerate(missing, start=1):
            target_id = item["target_id"]
            source_file = item.get("file") or self._resolve_source_file(target_id)
            suggested_test = item.get("suggested_test_file") or self._suggest_test_file(source_file or "")
            tasks.append({
                "task_id": idx,
                "target_id": target_id,
                "source_file": source_file,
                "suggested_test_file": suggested_test,
                "instructions": f"Write tests in {suggested_test} and verify runtime proof for {target_id}",
                "context_command": f'python skills/softgnn-advisor/scripts/get_target_context.py --target "{target_id}"',
                "verify_command": f'python skills/softgnn-advisor/scripts/verify_runtime_proof.py --target "{target_id}" --test "{suggested_test}"',
            })
        return {
            "status": "success",
            "total_tasks": len(tasks),
            "project": self.project,
            "tasks": tasks,
        }

    # Helper methods for Python AST and symbol mappings

    def _resolve_source_file(self, target_id):
        import pandas as pd
        nodes_path = self.paths['NODES_DATA_PATH']
        if os.path.exists(nodes_path):
            try:
                df = pd.read_csv(nodes_path)
                match = df[df['id'].astype(str) == str(target_id)]
                if not match.empty:
                    file_val = match.iloc[0].get('file')
                    if pd.notna(file_val) and str(file_val).strip():
                        return str(file_val).strip()
            except Exception:
                pass

        # Try Universal Parser across repo files
        fn_ranges = UniversalASTParser(self.repo_path).collect_function_ranges()
        for f, fns in fn_ranges.items():
            if any(fn['function_id'] == target_id or fn['name'] == target_id.replace('FUNC:', '') for fn in fns):
                return f
        return None

    def _query_graph_relations(self, target_id):
        callers, callees = [], []
        import networkx as nx
        import pickle
        graph_path = self.paths['GRAPH_PATH']
        if os.path.exists(graph_path):
            try:
                with open(graph_path, 'rb') as f:
                    G = pickle.load(f)
                if G.has_node(target_id):
                    for u, v, data in G.in_edges(target_id, data=True):
                        rel = data.get('relation', '')
                        if 'CALL' in rel.upper() or 'USES' in rel.upper():
                            callers.append(u)
                    for u, v, data in G.out_edges(target_id, data=True):
                        rel = data.get('relation', '')
                        if 'CALL' in rel.upper() or 'USES' in rel.upper():
                            callees.append(v)
            except Exception:
                pass
        return callers[:20], callees[:20]

    def _suggest_test_file(self, source_file):
        normalized = (source_file or '').replace('\\', '/').strip('/')
        if not normalized:
            return 'tests/test_generated.py'
        parts = normalized.split('/')
        filename = parts[-1]
        name, ext = os.path.splitext(filename)

        if ext in ('.ts', '.tsx'):
            return f'tests/{name}.test.ts'
        elif ext in ('.js', '.jsx'):
            return f'tests/{name}.test.js'
        elif ext == '.go':
            return f"{'/'.join(parts[:-1])}/{name}_test.go" if len(parts) > 1 else f"{name}_test.go"

        test_filename = f'test_{name}.py'
        if len(parts) > 1 and parts[0] in ('src', 'softgnn_advisor', 'lib', 'app'):
            sub_path = '/'.join(parts[1:-1])
            if sub_path:
                return f'tests/{sub_path}/{test_filename}'
        return f'tests/{test_filename}'

    def _module_path(self, source_file):
        normalized = (source_file or '').replace('\\', '/').strip('/')
        for prefix in ('src/', 'lib/'):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
        if normalized.endswith('.py'):
            normalized = normalized[:-3]
        return normalized.replace('/', '.')

    def _parse_ast_context(self, source_code, target_id, source_file):
        result = {'source': '', 'signature': '', 'docstring': '', 'imports': []}
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            result['source'] = source_code
            return result

        lines = source_code.splitlines()
        for node in getattr(tree, 'body', []):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                result['imports'].append(self._slice_source(lines, node))

        qualname = target_id.replace('FUNC:', '')
        parts = qualname.split('.')

        target_node = None
        if len(parts) >= 2:
            class_name, method_name = parts[-2], parts[-1]
            for node in getattr(tree, 'body', []):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    for child in node.body:
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                            target_node = child
                            break
        else:
            func_name = parts[-1]
            for node in getattr(tree, 'body', []):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                    target_node = node
                    break

        if target_node:
            result['source'] = self._slice_source(lines, target_node)
            result['docstring'] = ast.get_docstring(target_node) or ''
            result['signature'] = self._get_signature(target_node)
        else:
            result['source'] = source_code

        return result

    @staticmethod
    def _slice_source(lines, node):
        start = max(0, getattr(node, 'lineno', 1) - 1)
        end = getattr(node, 'end_lineno', len(lines))
        return '\n'.join(lines[start:end])

    @staticmethod
    def _get_signature(node):
        args_str = []
        for arg in getattr(node.args, 'posonlyargs', []):
            args_str.append(arg.arg)
        if getattr(node.args, 'posonlyargs', []):
            args_str.append('/')
        for arg in node.args.args:
            args_str.append(arg.arg)
        if node.args.vararg:
            args_str.append(f'*{node.args.vararg.arg}')
        for arg in getattr(node.args, 'kwonlyargs', []):
            args_str.append(arg.arg)
        if node.args.kwarg:
            args_str.append(f'**{node.args.kwarg.arg}')
        return f"def {node.name}({', '.join(args_str)})"

    def predict_impact(self, target_symbol: str, mode: str = "hybrid", threshold: float = 0.1) -> dict:
        """Query direct dependents and latent HGT blast radius for a target symbol."""
        if self.language != "python":
            return {
                "status": "warning",
                "message": f"Impact prediction currently supports Python graphs (detected {self.language}).",
                "target": target_symbol,
                "direct_dependents": [],
                "latent_risk_candidates": [],
            }

        self.ensure_initialized(auto_etl=True)
        try:
            from softgnn_advisor.core.impact_engine import ImpactEngine
            engine = ImpactEngine(self.project)
            result = engine.analyze(target_symbol, mode=mode)
        except Exception as exc:
            return {
                "status": "error",
                "message": f"Failed to predict impact: {exc}",
                "target": target_symbol,
                "direct_dependents": [],
                "latent_risk_candidates": [],
            }

        if result is None:
            return {
                "status": "warning",
                "message": f"Target symbol '{target_symbol}' could not be resolved in the project graph.",
                "target": target_symbol,
                "direct_impact_count": 0,
                "direct_dependents": [],
                "latent_risk_candidates": [],
            }

        direct_deps = [
            {
                "symbol": c.label,
                "type": c.node_type,
                "score": round(c.final_score, 4),
                "relation": ", ".join(c.relations[:2]) if c.relations else "direct dependency",
                "path": c.paths[0] if c.paths else "",
            }
            for c in result.candidates if "Direct" in c.tiers
        ]

        latent_candidates = [
            {
                "symbol": c.label,
                "type": c.node_type,
                "score": round(c.final_score, 4),
                "gnn_score": round(c.gnn_score, 4),
                "relation": ", ".join(c.relations[:2]) or "Latent GNN Correlation",
                "path": c.paths[0] if c.paths else "",
            }
            for c in result.candidates if "Direct" not in c.tiers
        ]

        return {
            "status": "success",
            "project": self.project,
            "target": result.target.full_id,
            "target_type": result.target.node_type,
            "mode": result.mode,
            "direct_impact_count": result.direct_count,
            "direct_dependents": direct_deps,
            "latent_risk_candidates": latent_candidates,
            "warnings": result.warnings,
        }

    def triage_bug(self, query: str, max_devs: int = 3, max_files: int = 5) -> dict:
        """Recommend best-suited engineers and related files for a bug description or PR change."""
        self.ensure_initialized(auto_etl=True)
        from softgnn_advisor.core.triage_engine import TriageEngine
        engine = TriageEngine(self.project, self.repo_path)
        return engine.triage(query, max_devs=max_devs, max_files=max_files)

    def train_gnn(self) -> dict:
        """Trigger HGT Graph AI training for the current project."""
        self.ensure_initialized(auto_etl=True)
        try:
            from softgnn_advisor.scripts.train_model import run_optimization
        except ImportError as exc:
            return {
                "status": "error",
                "message": f"Training requires GNN dependencies: {exc}. Install with `pip install softgnn-advisor[gnn]`",
            }

        import time
        start_time = time.time()
        try:
            run_optimization(self.project)
            duration = round(time.time() - start_time, 2)
            meta = load_metadata(self.paths['METADATA_PATH'])
            return {
                "status": "success",
                "project": self.project,
                "duration_seconds": duration,
                "best_val_auc": meta.get("best_val_auc"),
                "test_auc": meta.get("test_auc"),
                "message": f"HGT model trained successfully in {duration}s (Test AUC: {meta.get('test_auc')}).",
            }
        except Exception as exc:
            return {
                "status": "error",
                "project": self.project,
                "message": f"Training failed: {exc}",
            }

