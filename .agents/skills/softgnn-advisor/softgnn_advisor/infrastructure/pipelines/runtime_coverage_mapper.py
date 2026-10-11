import ast
import json
import os
import pickle
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import networkx as nx

from softgnn_advisor.config.settings import get_project_paths
from softgnn_advisor.core.metadata_utils import load_metadata, save_metadata, utc_now_iso
from softgnn_advisor.scripts.etl_run import HAS_GNN_DEPS, convert_nx_to_pyg


@dataclass
class RuntimeCoverageEdge:
    test_id: str
    target_id: str
    relation: str
    confidence: float
    source_file: str
    covered_lines: list
    function_range: list
    coverage_context: str
    covered_line_count: int
    function_line_count: int
    covered_fraction: float
    mode: str


@dataclass
class RuntimeCoverageResult:
    discovered_tests: list
    passed_tests: int
    failed_tests: int
    runtime_edges: list
    warnings: list
    mode_used: str
    persisted: bool


class RuntimeCoverageMapper:
    def __init__(self, project, repo_path=None, coverage_dir=None):
        self.project = project
        self.paths = get_project_paths(project)
        self.repo_path = os.path.abspath(repo_path or self._metadata_source_path() or os.getcwd())
        self.coverage_dir = Path(coverage_dir or self.paths['COVERAGE_WORK_DIR'])
        self.coverage_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.paths['GRAPH_PATH']
        self.pyg_path = self.paths['PYG_DATA_PATH']
        self.nodes_data_path = self.paths['NODES_DATA_PATH']
        self.metadata_path = self.paths['METADATA_PATH']
        self.evidence_path = self.paths['RUNTIME_TEST_COVERAGE_EDGES_PATH']
        self.graph = self._load_graph()

    def map_runtime_coverage(self, pytest_args='tests', mode='auto', persist=True, max_tests=None):
        warnings = []
        tests = self._discover_tests(pytest_args, warnings)
        if max_tests:
            tests = tests[:max_tests]
        if not tests:
            self._write_evidence([])
            return RuntimeCoverageResult([], 0, 0, [], warnings or ['No pytest tests discovered.'], mode, persist)

        function_ranges = self._collect_function_ranges()
        context_lines = {}
        mode_used = mode
        if mode in ('auto', 'dynamic-context'):
            context_lines = self._run_dynamic_context_coverage(pytest_args, warnings)
            usable = self._has_mappable_contexts(context_lines, tests)
            if not usable:
                msg = 'Dynamic-context coverage did not produce usable per-test contexts.'
                warnings.append(msg)
                if mode == 'dynamic-context':
                    self._write_evidence([])
                    return RuntimeCoverageResult(tests, 0, len(tests), [], warnings, mode, persist)
                mode_used = 'per-test'
                context_lines = self._run_per_test_coverage(tests, warnings)
            else:
                mode_used = 'dynamic-context'
        elif mode == 'per-test':
            context_lines = self._run_per_test_coverage(tests, warnings)
        else:
            raise ValueError("mode must be one of: auto, dynamic-context, per-test")

        edges = self._build_runtime_edges(context_lines, function_ranges, mode_used)
        unique_edges = self._dedupe_edges(edges)
        if persist:
            self._persist_edges(unique_edges)
        self._write_evidence([asdict(e) for e in unique_edges])
        passed_tests = len({e.test_id for e in unique_edges})
        failed_tests = max(0, len(tests) - passed_tests)
        return RuntimeCoverageResult(tests, passed_tests, failed_tests, unique_edges, warnings, mode_used, persist)

    def _metadata_source_path(self):
        metadata = load_metadata(self.paths['METADATA_PATH'])
        return metadata.get('source_path')

    def _load_graph(self):
        if not os.path.exists(self.graph_path):
            return nx.MultiDiGraph()
        with open(str(self.graph_path), 'rb') as f:
            return pickle.load(f)

    def _discover_tests(self, pytest_args, warnings):
        cmd = [sys.executable, '-m', 'pytest', '--collect-only', '-q'] + self._split_args(pytest_args)
        proc = self._run(cmd, warnings, check=False)
        tests = []
        for line in proc.stdout.splitlines():
            line = line.strip().replace('\\', '/')
            if not line or line.startswith('<') or '::' not in line:
                continue
            if line.endswith(']') and '[' in line:
                # keep parameterized id as-is; pytest accepts it.
                pass
            tests.append(line)
        return list(dict.fromkeys(tests))

    def _run_dynamic_context_coverage(self, pytest_args, warnings):
        cov_file = self.coverage_dir / '.coverage.dynamic'
        json_path = self.coverage_dir / 'coverage_dynamic.json'
        plugin_path = self.coverage_dir / '_softgnn_cov_plugin.py'
        plugin_code = (
            "def pytest_runtest_call(item):\n"
            "    try:\n"
            "        import coverage\n"
            "        cov = coverage.Coverage.current()\n"
            "        if cov:\n"
            "            cov.switch_context(item.nodeid)\n"
            "    except Exception:\n"
            "        pass\n"
        )
        plugin_path.write_text(plugin_code, encoding='utf-8')

        env = os.environ.copy()
        env['COVERAGE_FILE'] = str(cov_file)
        env['PYTHONPATH'] = str(self.coverage_dir) + os.pathsep + env.get('PYTHONPATH', '')

        self._run([sys.executable, '-m', 'coverage', 'erase'], warnings, env=env, check=False)
        run_cmd = [
            sys.executable, '-m', 'coverage', 'run',
            '-m', 'pytest',
            '-p', '_softgnn_cov_plugin',
        ] + self._split_args(pytest_args)
        self._run(run_cmd, warnings, env=env, check=False)
        self._run([sys.executable, '-m', 'coverage', 'json', '--show-contexts', '-o', str(json_path)], warnings, env=env, check=False)
        return self._parse_context_coverage(json_path)

    def _run_per_test_coverage(self, tests, warnings):
        context_lines = {}
        for idx, test_id in enumerate(tests, start=1):
            cov_file = self.coverage_dir / f'.coverage.test_{idx}'
            json_path = self.coverage_dir / f'coverage_test_{idx}.json'
            env = os.environ.copy()
            env['COVERAGE_FILE'] = str(cov_file)
            self._run([sys.executable, '-m', 'coverage', 'erase'], warnings, env=env, check=False)
            proc = self._run([sys.executable, '-m', 'coverage', 'run', '-m', 'pytest', test_id], warnings, env=env, check=False)
            if proc.returncode != 0:
                warnings.append(f'pytest failed for {test_id}')
                continue
            self._run([sys.executable, '-m', 'coverage', 'json', '-o', str(json_path)], warnings, env=env, check=False)
            covered = self._parse_plain_coverage(json_path)
            normalized_test = self._context_to_test_id(test_id)
            for file_path, lines in covered.items():
                context_lines.setdefault(normalized_test, {}).setdefault(file_path, set()).update(lines)
        return context_lines

    def _parse_context_coverage(self, json_path):
        if not json_path.exists():
            return {}
        data = json.loads(json_path.read_text(encoding='utf-8'))
        context_lines = {}
        for file_path, file_data in data.get('files', {}).items():
            rel_path = self._rel_source_path(file_path)
            for line, contexts in file_data.get('contexts', {}).items():
                for context in contexts:
                    test_id = self._context_to_test_id(context)
                    if not test_id:
                        continue
                    context_lines.setdefault(test_id, {}).setdefault(rel_path, set()).add(int(line))
        return context_lines

    def _parse_plain_coverage(self, json_path):
        if not json_path.exists():
            return {}
        data = json.loads(json_path.read_text(encoding='utf-8'))
        covered = {}
        for file_path, file_data in data.get('files', {}).items():
            rel_path = self._rel_source_path(file_path)
            covered[rel_path] = set(file_data.get('executed_lines', []))
        return covered

    def _collect_function_ranges(self):
        ranges = {}
        for root, dirs, files in os.walk(self.repo_path):
            if '.venv' in root or '__pycache__' in root or '.git' in root:
                continue
            for file in files:
                if not file.endswith('.py'):
                    continue
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, self.repo_path).replace('\\', '/')
                try:
                    tree = ast.parse(Path(abs_path).read_text(encoding='utf-8'))
                except Exception:
                    continue
                ranges[rel_path] = self._ranges_from_tree(tree)
        return ranges

    def _ranges_from_tree(self, tree):
        ranges = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        ranges.append({
                            'function_id': f'FUNC:{node.name}.{child.name}',
                            'start': child.lineno,
                            'end': getattr(child, 'end_lineno', child.lineno),
                        })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                ranges.append({
                    'function_id': f'FUNC:{node.name}',
                    'start': node.lineno,
                    'end': getattr(node, 'end_lineno', node.lineno),
                })
        return ranges

    def _build_runtime_edges(self, context_lines, function_ranges, mode_used):
        edges = []
        for test_id, files in context_lines.items():
            for file_path, lines in files.items():
                for fn in function_ranges.get(file_path, []):
                    fn_lines = set(range(fn['start'], fn['end'] + 1))
                    covered = sorted(fn_lines.intersection(lines))
                    if not covered:
                        continue
                    function_line_count = max(1, fn['end'] - fn['start'] + 1)
                    edges.append(RuntimeCoverageEdge(
                        test_id=test_id,
                        target_id=fn['function_id'],
                        relation='executes_runtime',
                        confidence=1.0,
                        source_file=file_path,
                        covered_lines=covered,
                        function_range=[fn['start'], fn['end']],
                        coverage_context=test_id.replace('TEST:', ''),
                        covered_line_count=len(covered),
                        function_line_count=function_line_count,
                        covered_fraction=round(len(covered) / function_line_count, 4),
                        mode=mode_used,
                    ))
        return edges

    def _dedupe_edges(self, edges):
        deduped = {}
        for edge in edges:
            key = (edge.test_id, edge.target_id, edge.relation)
            if key not in deduped or len(edge.covered_lines) > len(deduped[key].covered_lines):
                deduped[key] = edge
        return list(deduped.values())

    def _persist_edges(self, edges):
        for edge in edges:
            if edge.test_id not in self.graph:
                self.graph.add_node(edge.test_id, type='TestFunction', name=edge.test_id.split('::')[-1], kind='test')
            if edge.target_id not in self.graph:
                self.graph.add_node(edge.target_id, type='Function', name=edge.target_id.replace('FUNC:', ''), kind='unknown')
            self.graph.add_edge(edge.test_id, edge.target_id, type='executes_runtime')
        with open(str(self.graph_path), 'wb') as f:
            pickle.dump(self.graph, f, pickle.HIGHEST_PROTOCOL)
        if HAS_GNN_DEPS:
            import torch
            hetero_data, node_mapping = convert_nx_to_pyg(self.graph)
            torch.save(hetero_data, str(self.pyg_path))
        else:
            from softgnn_advisor.scripts.etl_run import build_node_mapping
            node_mapping = build_node_mapping(self.graph)
        self._write_nodes_data(node_mapping)
        metadata = load_metadata(self.metadata_path)
        metadata.update({
            'runtime_coverage_mapped_at': utc_now_iso(),
            'runtime_coverage_edges': len(edges),
            'gnn_retrain_required': HAS_GNN_DEPS,
        })
        save_metadata(self.metadata_path, metadata)

    def _write_nodes_data(self, node_mapping):
        import pandas as pd
        rows = []
        for ntype, mapping in node_mapping.items():
            for node_id, pyg_id in mapping.items():
                attrs = self.graph.nodes[node_id]
                row = {
                    'id': node_id,
                    'type': ntype,
                    'name': attrs.get('name', str(node_id)),
                    'pyg_id': pyg_id,
                }
                for key in ('kind', 'is_project_defined', 'defined_in', 'module'):
                    value = attrs.get(key)
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        row[key] = value
                rows.append(row)
        pd.DataFrame(rows).to_csv(str(self.nodes_data_path), index=False)

    def _write_evidence(self, evidence):
        os.makedirs(os.path.dirname(str(self.evidence_path)), exist_ok=True)
        with open(str(self.evidence_path), 'w', encoding='utf-8') as f:
            json.dump(evidence, f, indent=2)

    def _has_mappable_contexts(self, context_lines, tests):
        if not context_lines:
            return False
        test_nodes = {self._context_to_test_id(t) for t in tests}
        return bool(set(context_lines).intersection(test_nodes))

    def _context_to_test_id(self, context):
        if not context:
            return None
        context = context.strip().replace('\\', '/')
        if context.startswith('TEST:'):
            return context
        if '::' not in context:
            return None
        parts = context.split('::')
        file_part = parts[0]
        if len(parts) == 2:
            name = parts[1]
        else:
            name = '.'.join(parts[1:])
        return f'TEST:{file_part}::{name}'

    def _rel_source_path(self, file_path):
        file_path = file_path.replace('\\', '/')
        abs_path = os.path.abspath(file_path)
        if os.path.isabs(file_path) and abs_path.startswith(self.repo_path):
            return os.path.relpath(abs_path, self.repo_path).replace('\\', '/')
        return file_path

    def _split_args(self, args):
        if not args:
            return []
        if isinstance(args, (list, tuple)):
            return list(args)
        return str(args).split()

    def _run(self, cmd, warnings, env=None, check=False):
        if shutil.which(cmd[0]) is None and cmd[0] != sys.executable:
            warnings.append(f'command not found: {cmd[0]}')
        proc = subprocess.run(
            cmd,
            cwd=self.repo_path,
            env=env,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
        if check and proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout)
        if proc.returncode != 0 and proc.stderr:
            warnings.append(proc.stderr.strip().splitlines()[-1])
        return proc

