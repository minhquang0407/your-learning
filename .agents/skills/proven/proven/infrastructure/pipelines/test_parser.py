import ast
import os
import re
from dataclasses import asdict, dataclass, field

import networkx as nx


@dataclass
class TestEdgeEvidence:
    source: str
    relation: str
    target: str
    confidence: float
    evidence: str


class TestGraphParser:
    def __init__(self, root_dir, project_symbols=None, contract_snapshot=None):
        self.root_dir = os.path.abspath(root_dir)
        self.project_symbols = project_symbols or {}
        self.contract_snapshot = contract_snapshot or {}
        self.graph = nx.MultiDiGraph()
        self.evidence = []

    def parse_all(self):
        for root, dirs, files in os.walk(self.root_dir):
            if '.venv' in root or '__pycache__' in root or '.git' in root:
                continue
            for file in files:
                if not self._is_test_file(file, root):
                    continue
                self._parse_test_file(os.path.join(root, file))
        return self.graph, [asdict(e) for e in self.evidence]

    def _is_test_file(self, file, root):
        if not file.endswith('.py'):
            return False
        rel_root = os.path.relpath(root, self.root_dir).replace('\\', '/')
        return file.startswith('test_') or file.endswith('_test.py') or rel_root.startswith('tests')

    def _parse_test_file(self, file_path):
        rel_path = os.path.relpath(file_path, self.root_dir).replace('\\', '/')
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source)
        except Exception:
            return

        file_id = f"TEST_FILE:{rel_path}"
        self.graph.add_node(file_id, type='TestFile', name=rel_path, defined_in=rel_path, kind='test')
        imports = self._extract_imports(tree, file_id)
        fixtures = self._extract_fixtures(tree, file_id, rel_path)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                self._add_test_function(file_id, rel_path, node, imports, fixtures)
            elif isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith('test_'):
                        self._add_test_function(file_id, rel_path, child, imports, fixtures, class_name=node.name)

    def _extract_imports(self, tree, file_id):
        imports = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.asname or alias.name.split('.')[0]] = alias.name
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    if alias.name == '*':
                        continue
                    local = alias.asname or alias.name
                    qualified = f"{module}.{alias.name}" if module else alias.name
                    imports[local] = qualified
                    target = self._resolve_symbol(alias.name, qualified)
                    if target:
                        self.graph.add_edge(file_id, target, type='imports')
        return imports

    def _extract_fixtures(self, tree, file_id, rel_path):
        fixtures = set()
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(self._decorator_name(d).endswith('fixture') for d in node.decorator_list):
                fixture_id = f"FIXTURE:{rel_path}::{node.name}"
                fixtures.add(node.name)
                self.graph.add_node(fixture_id, type='Fixture', name=node.name, defined_in=rel_path)
                self.graph.add_edge(file_id, fixture_id, type='defines')
        return fixtures

    def _add_test_function(self, file_id, rel_path, node, imports, fixtures, class_name=None):
        name = f"{class_name}.{node.name}" if class_name else node.name
        test_id = f"TEST:{rel_path}::{name}"
        assert_count = sum(1 for n in ast.walk(node) if isinstance(n, ast.Assert))
        used_fixtures = [arg.arg for arg in node.args.args if arg.arg in fixtures]
        self.graph.add_node(
            test_id,
            type='TestFunction',
            name=name,
            defined_in=rel_path,
            line_start=getattr(node, 'lineno', None),
            line_end=getattr(node, 'end_lineno', getattr(node, 'lineno', None)),
            assert_count=assert_count,
            fixtures=used_fixtures,
            kind='test',
        )
        self.graph.add_edge(file_id, test_id, type='defines')
        for fixture in used_fixtures:
            fixture_id = f"FIXTURE:{rel_path}::{fixture}"
            self.graph.add_node(fixture_id, type='Fixture', name=fixture, defined_in=rel_path)
            self.graph.add_edge(test_id, fixture_id, type='uses_fixture')

        assignments = self._assignment_types(node, imports)
        executed_targets = set()
        for call in [n for n in ast.walk(node) if isinstance(n, ast.Call)]:
            target = self._resolve_call(call, imports, assignments)
            if target:
                executed_targets.add(target)
                self.graph.add_edge(test_id, target, type='executes_static')
                self.evidence.append(TestEdgeEvidence(test_id, 'executes_static', target, 0.8, f"static call/import evidence in {rel_path}"))

        for target in self._name_based_targets(node.name):
            if target not in executed_targets:
                self.graph.add_edge(test_id, target, type='executes_static')
                self.evidence.append(TestEdgeEvidence(test_id, 'executes_static', target, 0.45, f"test name matches {target}"))

        if assert_count:
            for target in executed_targets:
                contract_id = self._current_contract_id(target)
                if contract_id:
                    relation = 'validates_static' if assert_count >= 2 else 'partially_validates_static'
                    self.graph.add_edge(test_id, contract_id, type=relation)
                    self.evidence.append(TestEdgeEvidence(test_id, relation, contract_id, 0.65, f"{assert_count} assert(s) after static execution evidence"))

    def _assignment_types(self, test_node, imports):
        assignments = {}
        for node in ast.walk(test_node):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                call_name = self._expr_name(node.value.func)
                class_target = self._resolve_symbol(call_name, imports.get(call_name, call_name))
                if class_target and class_target.startswith('CLASS:'):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            assignments[target.id] = class_target
        return assignments

    def _resolve_call(self, call, imports, assignments):
        call_name = self._expr_name(call.func)
        if not call_name:
            return None
        if call_name in assignments:
            class_id = assignments[call_name]
            func_id = f"FUNC:{class_id.replace('CLASS:', '')}.forward"
            return func_id if func_id in self.project_symbols.values() else class_id
        if '.' in call_name:
            root, attr = call_name.split('.', 1)
            if root in assignments:
                class_name = assignments[root].replace('CLASS:', '')
                func_id = f"FUNC:{class_name}.{attr}"
                if func_id in self.project_symbols.values():
                    return func_id
        return self._resolve_symbol(call_name, imports.get(call_name, call_name))

    def _resolve_symbol(self, local_name, qualified_name):
        if not local_name and not qualified_name:
            return None
        for candidate in (qualified_name, local_name):
            if candidate in self.project_symbols:
                return self.project_symbols[candidate]
            if candidate and '.' in candidate:
                simple = candidate.split('.')[-1]
                if simple in self.project_symbols:
                    return self.project_symbols[simple]
        return None

    def _name_based_targets(self, test_name):
        normalized = self._normalize(test_name.replace('test_', ''))
        matches = []
        for symbol, node_id in self.project_symbols.items():
            if not node_id.startswith(('FUNC:', 'CLASS:')):
                continue
            leaf = node_id.split(':', 1)[1]
            if self._normalize(leaf) in normalized:
                matches.append(node_id)
        return matches[:5]

    def _current_contract_id(self, function_id):
        if not function_id.startswith('FUNC:'):
            return None
        row = self.contract_snapshot.get(function_id) or {}
        return row.get('current_contract_id') or row.get('contract_id')

    def _expr_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = self._expr_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return None

    def _decorator_name(self, node):
        if isinstance(node, ast.Call):
            node = node.func
        return self._expr_name(node) or ''

    def _normalize(self, value):
        return re.sub(r'[^0-9a-z]+', '', value.lower())
