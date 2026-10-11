import ast
import builtins
import os
import networkx as nx


class CodebaseASTParser:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.graph = nx.MultiDiGraph()
        self.file_nodes = set()
        self.class_nodes = set()
        self.function_nodes = set()
        self.module_nodes = set()
        self.edges = []
        self.file_children = {}  # file_node_id -> {'functions': [...], 'classes': [...]}
        self.node_attrs = {}
        self.project_symbols = {}  # simple or qualified symbol -> node id
        self.module_to_file = {}  # import module path -> FILE node id
        self.builtin_names = set(dir(builtins))

    def parse_all(self):
        print(f"Scanning Codebase: {self.root_dir}")
        parsed_files = []
        for root, dirs, files in os.walk(self.root_dir):
            if '.venv' in root or '__pycache__' in root or '.git' in root:
                continue

            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    parsed = self._read_python_file(file_path)
                    if parsed:
                        parsed_files.append(parsed)
                        self._collect_project_definitions(*parsed)

        for file_path, rel_path, tree in parsed_files:
            self._parse_file(file_path, rel_path, tree)

        return self._build_graph()

    def _read_python_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Skipping {file_path}: {e}")
            return None

        try:
            tree = ast.parse(content)
        except SyntaxError:
            print(f"Syntax error in {file_path}")
            return None

        rel_path = os.path.relpath(file_path, self.root_dir).replace('\\', '/')
        return file_path, rel_path, tree

    def _module_name_from_rel_path(self, rel_path):
        if rel_path.endswith('/__init__.py'):
            rel_path = rel_path[:-len('/__init__.py')]
        elif rel_path.endswith('.py'):
            rel_path = rel_path[:-3]
        return rel_path.replace('/', '.')

    def _collect_project_definitions(self, file_path, rel_path, tree):
        file_node_id = f"FILE:{rel_path}"
        self.file_nodes.add(file_node_id)
        module_name = self._module_name_from_rel_path(rel_path)
        self.module_to_file[module_name] = file_node_id
        fc = self.file_children.setdefault(file_node_id, {'functions': [], 'classes': []})

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_id = f"CLASS:{node.name}"
                self.class_nodes.add(class_id)
                self.project_symbols[node.name] = class_id
                self.project_symbols[f"{module_name}.{node.name}"] = class_id
                fc['classes'].append(node.name)
                self.node_attrs[class_id] = {
                    'type': 'Class',
                    'name': node.name,
                    'kind': 'project',
                    'is_project_defined': True,
                    'defined_in': rel_path,
                    'module': module_name,
                }

                for body_node in node.body:
                    if isinstance(body_node, ast.FunctionDef):
                        func_name = f"{node.name}.{body_node.name}"
                        func_id = f"FUNC:{func_name}"
                        self.function_nodes.add(func_id)
                        self.project_symbols[func_name] = func_id
                        self.project_symbols[f"{module_name}.{func_name}"] = func_id
                        self.node_attrs[func_id] = {
                            'type': 'Function',
                            'name': func_name,
                            'kind': 'project',
                            'is_project_defined': True,
                            'defined_in': rel_path,
                            'module': module_name,
                        }

            elif isinstance(node, ast.FunctionDef):
                func_id = f"FUNC:{node.name}"
                self.function_nodes.add(func_id)
                self.project_symbols[node.name] = func_id
                self.project_symbols[f"{module_name}.{node.name}"] = func_id
                fc['functions'].append(node.name)
                self.node_attrs[func_id] = {
                    'type': 'Function',
                    'name': node.name,
                    'kind': 'project',
                    'is_project_defined': True,
                    'defined_in': rel_path,
                    'module': module_name,
                }

    def _parse_file(self, file_path, rel_path, tree):
        file_node_id = f"FILE:{rel_path}"
        self.file_nodes.add(file_node_id)
        self.file_children.setdefault(file_node_id, {'functions': [], 'classes': []})
        current_module = self._module_name_from_rel_path(rel_path)
        imports = self._extract_imports(tree, file_node_id, current_module)

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_id = f"CLASS:{node.name}"
                self.edges.append((file_node_id, 'defines', class_id))
                self._extract_inheritance(node, class_id, imports)

                for body_node in node.body:
                    if isinstance(body_node, ast.FunctionDef):
                        func_id = f"FUNC:{node.name}.{body_node.name}"
                        self.edges.append((class_id, 'defines', func_id))
                        self._extract_function_dependencies(body_node, func_id, imports)

            elif isinstance(node, ast.FunctionDef):
                func_id = f"FUNC:{node.name}"
                self.edges.append((file_node_id, 'defines', func_id))
                self._extract_function_dependencies(node, func_id, imports)

    def _resolve_relative_module(self, module_name, level, current_module):
        if level <= 0:
            return module_name
        parts = current_module.split('.')[:-level]
        if module_name:
            parts.extend(module_name.split('.'))
        return '.'.join(part for part in parts if part)

    def _ensure_module_node(self, module_name):
        module_id = f"MODULE:{module_name}"
        self.module_nodes.add(module_id)
        self.node_attrs[module_id] = {'type': 'Module', 'name': module_name, 'kind': 'external'}
        return module_id

    def _extract_imports(self, tree, file_node_id, current_module):
        imports = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local_name = alias.asname or alias.name.split('.')[0]
                    module_name = alias.name
                    imports[local_name] = module_name
                    target_file = self.module_to_file.get(module_name)
                    if target_file:
                        self.edges.append((file_node_id, 'imports', target_file))
                    else:
                        self.edges.append((file_node_id, 'imports', self._ensure_module_node(module_name)))

            elif isinstance(node, ast.ImportFrom):
                module_name = self._resolve_relative_module(node.module or '', node.level, current_module)
                target_file = self.module_to_file.get(module_name)
                if target_file:
                    self.edges.append((file_node_id, 'imports', target_file))
                elif module_name:
                    self.edges.append((file_node_id, 'imports', self._ensure_module_node(module_name)))

                for alias in node.names:
                    if alias.name == '*':
                        continue
                    local_name = alias.asname or alias.name
                    qualified_name = f"{module_name}.{alias.name}" if module_name else alias.name
                    imports[local_name] = qualified_name
                    symbol_id = self.project_symbols.get(qualified_name) or self.project_symbols.get(alias.name)
                    if symbol_id:
                        self.edges.append((file_node_id, 'imports', symbol_id))

        return imports

    def _expr_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = self._expr_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return None

    def _resolve_symbol(self, symbol_name, imports):
        if not symbol_name:
            return None, 'unknown', None

        root_name = symbol_name.split('.')[0]
        if symbol_name in self.project_symbols:
            return self.project_symbols[symbol_name], 'project', None
        if root_name in imports:
            imported = imports[root_name]
            resolved_name = symbol_name.replace(root_name, imported, 1)
            if resolved_name in self.project_symbols:
                return self.project_symbols[resolved_name], 'project', None
            if imported in self.project_symbols:
                return self.project_symbols[imported], 'project', None
            return f"FUNC:{resolved_name}", 'external', imported.split('.')[0]
        if root_name in self.project_symbols:
            return self.project_symbols[root_name], 'project', None
        if symbol_name in self.builtin_names:
            return f"FUNC:{symbol_name}", 'builtin', None
        if '.' in symbol_name:
            return f"FUNC:{symbol_name}", 'external', root_name
        return f"FUNC:{symbol_name}", 'unknown', None

    def _ensure_function_node(self, func_id, kind, module=None):
        self.function_nodes.add(func_id)
        self.node_attrs.setdefault(func_id, {
            'type': 'Function',
            'name': func_id.replace('FUNC:', ''),
            'kind': kind,
            'is_project_defined': kind == 'project',
            'defined_in': None,
            'module': module,
        })

    def _extract_inheritance(self, class_node, class_id, imports):
        for base in class_node.bases:
            base_name = self._expr_name(base)
            target_id, kind, module = self._resolve_symbol(base_name, imports)
            if not target_id:
                continue
            if target_id.startswith('CLASS:'):
                self.edges.append((class_id, 'inherits', target_id))
            else:
                module_id = self._ensure_module_node(module or base_name or target_id.replace('FUNC:', ''))
                self.edges.append((class_id, 'inherits', module_id))

    def _extract_function_dependencies(self, function_node, caller_id, imports):
        for node in ast.walk(function_node):
            if isinstance(node, ast.Call):
                call_name = self._expr_name(node.func)
                callee_id, kind, module = self._resolve_symbol(call_name, imports)
                if not callee_id:
                    continue

                if callee_id.startswith('CLASS:'):
                    self.edges.append((caller_id, 'instantiates', callee_id))
                    self.edges.append((caller_id, 'uses', callee_id))
                else:
                    self._ensure_function_node(callee_id, kind, module)
                    self.edges.append((caller_id, 'calls', callee_id))

            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                target_id, kind, module = self._resolve_symbol(node.id, imports)
                if target_id and target_id != caller_id and target_id.startswith('CLASS:'):
                    self.edges.append((caller_id, 'uses', target_id))

    def _build_graph(self):
        for f in self.file_nodes:
            children = self.file_children.get(f, {})
            self.graph.add_node(
                f,
                type='File',
                name=f.split(':', 1)[1],
                functions=children.get('functions', []),
                classes=children.get('classes', []),
                kind='project',
                is_project_defined=True,
                defined_in=f.split(':', 1)[1],
            )
        for c in self.class_nodes:
            attrs = self.node_attrs.get(c, {'type': 'Class', 'name': c.split(':', 1)[1]})
            self.graph.add_node(c, **attrs)
        for fn in self.function_nodes:
            attrs = self.node_attrs.get(fn, {
                'type': 'Function',
                'name': fn.split(':', 1)[1],
                'kind': 'unknown',
                'is_project_defined': False,
                'defined_in': None,
                'module': None,
            })
            self.graph.add_node(fn, **attrs)
        for module in self.module_nodes:
            attrs = self.node_attrs.get(module, {'type': 'Module', 'name': module.split(':', 1)[1], 'kind': 'external'})
            self.graph.add_node(module, **attrs)

        for src, rel, dst in self.edges:
            self.graph.add_edge(src, dst, type=rel)

        print(f"Extracted {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges.")
        return self.graph


if __name__ == '__main__':
    parser = CodebaseASTParser(".")
    G = parser.parse_all()
    print("Graph built successfully!")
