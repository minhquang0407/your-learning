import json
import os
import pickle
from collections import Counter, deque
from pathlib import Path

import pandas as pd

from softgnn_advisor.config.settings import get_project_paths


def _norm(path):
    return str(path or '').replace('\\', '/').strip()


def _label(node_id):
    text = str(node_id)
    if ':' in text:
        text = text.split(':', 1)[1]
    return text.split('/')[-1]


def _node_type_from_id(node_id, fallback='Unknown'):
    text = str(node_id)
    if ':' in text:
        prefix = text.split(':', 1)[0]
        mapping = {'FILE': 'File', 'CLASS': 'Class', 'FUNC': 'Function', 'TEST': 'TestFunction'}
        return mapping.get(prefix, prefix.title())
    return fallback


def _load_json(path, default):
    try:
        if path and os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _node_source(row):
    for key in ('source_file', 'file', 'path'):
        if key in row and not pd.isna(row[key]):
            return _norm(row[key])
    node_id = str(row.get('id', ''))
    if node_id.startswith('FILE:'):
        return _norm(node_id.replace('FILE:', '', 1))
    return ''


def _load_nodes(paths):
    nodes = {}
    if os.path.exists(paths['NODES_DATA_PATH']):
        df = pd.read_csv(paths['NODES_DATA_PATH'])
        for _, row in df.iterrows():
            data = row.to_dict()
            node_id = str(data.get('id') or data.get('name') or '')
            if not node_id:
                continue
            ntype = str(data.get('type') or _node_type_from_id(node_id))
            nodes[node_id] = {
                'id': node_id,
                'label': _label(data.get('name') or node_id),
                'type': ntype,
                'source_file': _node_source(data),
                'coverage': 'unknown',
            }
    return nodes


def _load_graph_edges(paths, nodes):
    edges = []
    if not os.path.exists(paths['GRAPH_PATH']):
        return edges
    try:
        with open(paths['GRAPH_PATH'], 'rb') as f:
            graph = pickle.load(f)
        for u, v, data in graph.edges(data=True):
            source, target = str(u), str(v)
            if source not in nodes:
                nodes[source] = {'id': source, 'label': _label(source), 'type': _node_type_from_id(source), 'source_file': '', 'coverage': 'unknown'}
            if target not in nodes:
                nodes[target] = {'id': target, 'label': _label(target), 'type': _node_type_from_id(target), 'source_file': '', 'coverage': 'unknown'}
            edges.append({'source': source, 'target': target, 'type': str(data.get('type', 'linked'))})
    except Exception as exc:
        edges.append({'source': '__error__', 'target': '__error__', 'type': f'graph-load-error:{exc}'})
    return edges


def _apply_coverage(paths, nodes, edges):
    static_edges = _load_json(paths.get('TEST_COVERAGE_EDGES_PATH'), [])
    runtime_edges = _load_json(paths.get('RUNTIME_TEST_COVERAGE_EDGES_PATH'), [])
    for item in static_edges if isinstance(static_edges, list) else []:
        target = item.get('target_id') or item.get('target')
        test = item.get('test_id') or item.get('test')
        if target in nodes:
            nodes[target]['coverage'] = 'static'
        if test and target:
            nodes.setdefault(test, {'id': test, 'label': _label(test), 'type': 'TestFunction', 'source_file': item.get('test_file', ''), 'coverage': 'test'})
            edges.append({'source': test, 'target': target, 'type': 'static-covers'})
    for item in runtime_edges if isinstance(runtime_edges, list) else []:
        target = item.get('target_id') or item.get('target')
        test = item.get('test_id') or item.get('test')
        if target in nodes:
            nodes[target]['coverage'] = 'runtime-proven'
        if test and target:
            nodes.setdefault(test, {'id': test, 'label': _label(test), 'type': 'TestFunction', 'source_file': item.get('test_file', ''), 'coverage': 'test'})
            edges.append({'source': test, 'target': target, 'type': 'runtime-covers'})


def _slice(nodes, edges, focus=None, target=None, depth=1, max_nodes=500):
    focus = _norm(focus)
    start = set()
    if target:
        if target in nodes:
            start.add(target)
    elif focus:
        for node_id, node in nodes.items():
            if _norm(node.get('source_file')) == focus or node_id == f'FILE:{focus}':
                start.add(node_id)
    if not start:
        return set(list(nodes)[:max_nodes])
    adj = {node_id: set() for node_id in nodes}
    for edge in edges:
        s, t = edge['source'], edge['target']
        if s in nodes and t in nodes:
            adj.setdefault(s, set()).add(t)
            adj.setdefault(t, set()).add(s)
    seen = set(start)
    q = deque((node_id, 0) for node_id in start)
    while q and len(seen) < max_nodes:
        node_id, dist = q.popleft()
        if dist >= depth:
            continue
        for nxt in adj.get(node_id, ()):
            if nxt not in seen:
                seen.add(nxt)
                q.append((nxt, dist + 1))
                if len(seen) >= max_nodes:
                    break
    return seen


def export_graph(project, focus=None, target=None, depth=1, max_nodes=500):
    paths = get_project_paths(project)
    nodes = _load_nodes(paths)
    edges = _load_graph_edges(paths, nodes)
    _apply_coverage(paths, nodes, edges)
    keep = _slice(nodes, edges, focus=focus, target=target, depth=max(0, int(depth or 0)), max_nodes=max_nodes)
    visible_nodes = [nodes[node_id] for node_id in keep if node_id in nodes]
    visible_edges = [e for e in edges if e.get('source') in keep and e.get('target') in keep and not e.get('source', '').startswith('__error__')]
    counts = Counter(node.get('type', 'Unknown') for node in visible_nodes)
    return {
        'project': project,
        'focus': focus,
        'target': target,
        'summary': {
            'nodes': len(visible_nodes),
            'edges': len(visible_edges),
            'files': counts.get('File', 0),
            'classes': counts.get('Class', 0),
            'functions': counts.get('Function', 0),
            'tests': counts.get('TestFunction', 0) + counts.get('Test', 0),
            'runtime_edges': sum(1 for e in visible_edges if e.get('type') == 'runtime-covers'),
        },
        'nodes': visible_nodes,
        'edges': visible_edges,
    }
