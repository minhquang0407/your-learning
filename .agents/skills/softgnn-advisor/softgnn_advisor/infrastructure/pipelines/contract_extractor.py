import ast
import hashlib
import json
import os
from dataclasses import asdict, dataclass, field

import networkx as nx


@dataclass
class ContractInfo:
    function_id: str
    contract_id: str
    signature: str
    signature_hash: str
    return_pattern_hash: str
    behavior_hash: str
    source_hash: str
    contract_hash: str
    args: list = field(default_factory=list)
    defaults: dict = field(default_factory=dict)
    return_annotation: str = None
    return_patterns: list = field(default_factory=list)
    docstring_hash: str = None
    defined_in: str = None


class ContractExtractor:
    def __init__(self, root_dir):
        self.root_dir = os.path.abspath(root_dir)

    def extract_all(self):
        contracts = {}
        for root, dirs, files in os.walk(self.root_dir):
            if '.venv' in root or '__pycache__' in root or '.git' in root:
                continue
            for file in files:
                if not file.endswith('.py'):
                    continue
                path = os.path.join(root, file)
                rel_path = os.path.relpath(path, self.root_dir).replace('\\', '/')
                contracts.update(self.extract_file(path, rel_path))
        return contracts

    def extract_file(self, file_path, rel_path=None):
        rel_path = rel_path or os.path.relpath(file_path, self.root_dir).replace('\\', '/')
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source)
        except Exception:
            return {}

        contracts = {}
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        function_id = f"FUNC:{node.name}.{child.name}"
                        contracts[function_id] = self._contract_for_function(function_id, child, source, rel_path)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_id = f"FUNC:{node.name}"
                contracts[function_id] = self._contract_for_function(function_id, node, source, rel_path)
        return contracts

    def build_graph_and_snapshot(self, current_contracts, previous_snapshot=None):
        previous_snapshot = previous_snapshot or {}
        graph = nx.MultiDiGraph()
        snapshot = {}
        for function_id, info in current_contracts.items():
            graph.add_node(info.contract_id, type='ContractVersion', name=info.contract_id.replace('CONTRACT:', ''), **asdict(info))
            graph.add_edge(function_id, info.contract_id, type='has_contract')
            old = previous_snapshot.get(function_id)
            if old and old.get('contract_hash') != info.contract_hash:
                old_id = old.get('current_contract_id') or old.get('contract_id')
                if old_id:
                    graph.add_node(old_id, type='ContractVersion', name=old_id.replace('CONTRACT:', ''), **old)
                    graph.add_edge(info.contract_id, old_id, type='supersedes')
            row = asdict(info)
            row['current_contract_id'] = info.contract_id
            snapshot[function_id] = row
        return graph, snapshot

    def diff_contracts(self, old, new):
        if not old or not new:
            return {}
        return {
            'signature_changed': old.get('signature_hash') != new.signature_hash,
            'return_pattern_changed': old.get('return_pattern_hash') != new.return_pattern_hash,
            'behavior_changed': old.get('behavior_hash') != new.behavior_hash,
            'source_only_changed': old.get('source_hash') != new.source_hash and old.get('behavior_hash') == new.behavior_hash,
            'old': old,
            'new': asdict(new),
        }

    def _contract_for_function(self, function_id, node, source, rel_path):
        signature = self._signature(node)
        signature_hash = self._hash(signature)
        return_patterns = self._return_patterns(node)
        return_pattern_hash = self._hash(json.dumps(return_patterns, sort_keys=True))
        docstring = ast.get_docstring(node) or ''
        docstring_hash = self._hash(docstring)
        behavior_hash = self._hash('|'.join([signature_hash, return_pattern_hash, docstring_hash]))
        source_segment = ast.get_source_segment(source, node) or ast.dump(node, include_attributes=False)
        source_hash = self._hash(ast.dump(node, include_attributes=False))
        contract_hash = behavior_hash
        contract_id = f"CONTRACT:{function_id.replace('FUNC:', '')}@{contract_hash[:12]}"
        args, defaults = self._args_and_defaults(node)
        return_annotation = ast.unparse(node.returns) if node.returns else None
        return ContractInfo(
            function_id=function_id,
            contract_id=contract_id,
            signature=signature,
            signature_hash=signature_hash,
            return_pattern_hash=return_pattern_hash,
            behavior_hash=behavior_hash,
            source_hash=source_hash,
            contract_hash=contract_hash,
            args=args,
            defaults=defaults,
            return_annotation=return_annotation,
            return_patterns=return_patterns,
            docstring_hash=docstring_hash,
            defined_in=rel_path,
        )

    def _signature(self, node):
        args = []
        all_args = list(node.args.posonlyargs) + list(node.args.args)
        default_offset = len(all_args) - len(node.args.defaults)
        defaults_by_index = {default_offset + i: ast.unparse(d) for i, d in enumerate(node.args.defaults)}
        for idx, arg in enumerate(all_args):
            text = arg.arg
            if arg.annotation:
                text += f":{ast.unparse(arg.annotation)}"
            if idx in defaults_by_index:
                text += f"={defaults_by_index[idx]}"
            args.append(text)
        if node.args.vararg:
            args.append('*' + node.args.vararg.arg)
        for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            text = arg.arg
            if arg.annotation:
                text += f":{ast.unparse(arg.annotation)}"
            if default:
                text += f"={ast.unparse(default)}"
            args.append(text)
        if node.args.kwarg:
            args.append('**' + node.args.kwarg.arg)
        ret = ast.unparse(node.returns) if node.returns else 'None'
        return f"{node.name}({','.join(args)})->{ret}"

    def _args_and_defaults(self, node):
        all_args = list(node.args.posonlyargs) + list(node.args.args)
        args = [a.arg for a in all_args]
        defaults = {}
        default_offset = len(all_args) - len(node.args.defaults)
        for idx, default in enumerate(node.args.defaults):
            defaults[all_args[default_offset + idx].arg] = ast.unparse(default)
        return args, defaults

    def _return_patterns(self, node):
        patterns = []
        for item in ast.walk(node):
            if isinstance(item, ast.Return):
                patterns.append(self._return_pattern(item.value))
            elif isinstance(item, ast.Raise):
                patterns.append({'kind': 'Raise'})
            elif isinstance(item, (ast.Yield, ast.YieldFrom)):
                patterns.append({'kind': 'Yield'})
        return patterns or [{'kind': 'None'}]

    def _return_pattern(self, value):
        if value is None:
            return {'kind': 'None'}
        if isinstance(value, ast.Dict):
            keys = []
            for key in value.keys:
                if isinstance(key, ast.Constant):
                    keys.append(str(key.value))
                elif key is not None:
                    keys.append(ast.unparse(key))
            return {'kind': 'Dict', 'keys': keys}
        if isinstance(value, ast.Tuple):
            return {'kind': 'Tuple', 'length': len(value.elts)}
        if isinstance(value, ast.List):
            return {'kind': 'List', 'length': len(value.elts)}
        if isinstance(value, ast.Constant):
            return {'kind': type(value.value).__name__, 'value': repr(value.value)}
        if isinstance(value, ast.Name):
            return {'kind': 'Name'}
        if isinstance(value, ast.Call):
            return {'kind': 'Call', 'func': ast.unparse(value.func)}
        return {'kind': type(value).__name__}

    def _hash(self, text):
        return hashlib.sha256((text or '').encode('utf-8')).hexdigest()


def load_contract_snapshot(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_contract_snapshot(path, snapshot):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)
