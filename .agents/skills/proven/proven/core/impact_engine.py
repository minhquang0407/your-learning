import os
from collections import defaultdict
from dataclasses import dataclass, field

import pandas as pd

from proven.config.settings import get_project_paths
from proven.core.file_filters import is_source_code_file
from proven.core.metadata_utils import load_metadata


@dataclass
class ImpactTarget:
    key: tuple
    full_id: str
    node_type: str


@dataclass
class ImpactCandidate:
    key: tuple
    label: str
    node_type: str
    final_score: float
    rule_score: float
    gnn_score: float
    tiers: list = field(default_factory=list)
    relations: list = field(default_factory=list)
    paths: list = field(default_factory=list)


@dataclass
class ImpactResult:
    target: ImpactTarget
    internal_members: list
    candidates: list
    mode: str
    gnn_type_filter: set
    direct_count: int
    warnings: list = field(default_factory=list)


class ImpactEngine:
    def __init__(self, project):
        self.project = project
        self.paths = get_project_paths(project)
        self.pyg_data_path = self.paths['PYG_DATA_PATH']
        self.nodes_data_path = self.paths['NODES_DATA_PATH']
        self.metadata_path = self.paths['METADATA_PATH']
        self.model_path = self.paths['MODEL_PATH']
        if not os.path.exists(self.nodes_data_path):
            raise FileNotFoundError(f"Data not found for project '{project}'. Run softgnn setup first.")

        self.df = pd.read_csv(self.nodes_data_path)
        self.df['name_str'] = self.df['name'].astype(str)
        self.df['id_str'] = self.df['id'].astype(str)
        self.metadata = load_metadata(self.metadata_path)
        self.source_path = self.metadata.get('source_path')

        self.row_by_key = {}
        self.name_by_key = {}
        self.full_id_by_key = {}
        self.key_by_full_id = {}
        for _, row in self.df.iterrows():
            key = (str(row['type']), int(row['pyg_id']))
            self.row_by_key[key] = row
            self.name_by_key[key] = str(row['name'])
            self.full_id_by_key[key] = str(row['id'])
            self.key_by_full_id[str(row['id'])] = key

        self.data = None
        if os.path.exists(self.pyg_data_path):
            try:
                import torch
                self.data = torch.load(self.pyg_data_path, map_location='cpu', weights_only=False)
            except ImportError:
                self.data = None
        if self.data is None:
            self.data = self._load_networkx_data()

        self.out_edges = defaultdict(list)
        self.in_edges = defaultdict(list)
        for edge_type in self._iter_edge_types():
            src_t, rel, dst_t = edge_type
            edge_index = self._edge_index_for(edge_type)
            for src, dst in edge_index:
                src_key = (src_t, int(src))
                dst_key = (dst_t, int(dst))
                self.out_edges[src_key].append((rel, dst_key))
                self.in_edges[dst_key].append((rel, src_key))

        self.project_defined_functions = {
            dst_key
            for src_key, edges in self.out_edges.items()
            for rel, dst_key in edges
            if rel == 'defines' and dst_key[0] == 'Function' and src_key[0] in {'File', 'Class'}
        }

    def _load_networkx_data(self):
        import pickle
        if not os.path.exists(self.paths['GRAPH_PATH']):
            raise FileNotFoundError(f"Data not found for project '{self.project}'. Run softgnn setup first.")
        with open(self.paths['GRAPH_PATH'], 'rb') as f:
            graph = pickle.load(f)
        edge_map = defaultdict(list)
        for u, v, d in graph.edges(data=True):
            src = self.key_by_full_id.get(str(u))
            dst = self.key_by_full_id.get(str(v))
            if src is None or dst is None:
                continue
            rel = d.get('type', 'linked')
            edge_map[(src[0], rel, dst[0])].append((src[1], dst[1]))
        return edge_map

    def _iter_edge_types(self):
        return self.data.edge_types if hasattr(self.data, 'edge_types') else list(self.data.keys())

    def _edge_index_for(self, edge_type):
        if hasattr(self.data, 'edge_types'):
            return self.data[edge_type].edge_index.t().tolist()
        return self.data.get(edge_type, [])

    def display_node_label(self, key):
        full_id = self.full_id_by_key.get(key, str(key))
        if full_id.startswith('FUNC:'):
            func_name = full_id.replace('FUNC:', '', 1)
            if '.' in func_name:
                class_name, method_name = func_name.rsplit('.', 1)
                return f"{method_name} ({class_name})"
            return func_name
        if full_id.startswith('CLASS:'):
            return full_id.replace('CLASS:', '', 1)
        if full_id.startswith('FILE:'):
            return full_id.replace('FILE:', '', 1)
        return self.name_by_key.get(key, full_id)

    def resolve_target(self, query):
        matches = self.df[
            self.df['type'].isin(['File', 'Function', 'Class']) &
            (
                self.df['name_str'].str.contains(query, case=False, na=False) |
                self.df['id_str'].str.contains(query, case=False, na=False)
            )
        ].copy()
        if matches.empty:
            return None
        type_priority = {'File': 0, 'Class': 1, 'Function': 2}
        matches['priority'] = matches['type'].map(type_priority).fillna(99)
        matches['exact'] = (matches['name_str'].str.lower() == query.lower()).astype(int)
        matches = matches.sort_values(['exact', 'priority'], ascending=[False, True])
        row = matches.iloc[0]
        key = (str(row['type']), int(row['pyg_id']))
        return ImpactTarget(key=key, full_id=str(row['id']), node_type=key[0])

    def is_existing_source_file(self, file_key):
        if file_key[0] != 'File':
            return True
        rel = self.full_id_by_key.get(file_key, '').replace('FILE:', '')
        if not is_source_code_file(rel):
            return False
        if self.source_path:
            return os.path.exists(os.path.join(self.source_path, rel.replace('/', os.sep)))
        return True

    def is_project_candidate(self, key):
        if key[0] == 'Function':
            row = self.row_by_key.get(key)
            if row is not None and 'is_project_defined' in row and str(row.get('is_project_defined')).lower() in {'true', '1'}:
                return True
            return key in self.project_defined_functions
        if key[0] == 'File':
            return self.is_existing_source_file(key)
        if key[0] == 'Class':
            return True
        return False

    def _add_score(self, scores, target_key, key, amount, tier, relation, path):
        if key == target_key or not self.is_project_candidate(key):
            return
        scores[key]['score'] += amount
        scores[key]['tiers'].append(tier)
        scores[key]['relations'].append(relation)
        scores[key]['paths'].append(path)

    def analyze(self, query_or_key, mode='deterministic', gnn_types='File,Class,Function', limit=10, status_callback=None):
        target = query_or_key if isinstance(query_or_key, ImpactTarget) else self.resolve_target(query_or_key)
        if target is None:
            return None
        mode = mode or 'deterministic'
        gnn_type_filter = {t.strip() for t in gnn_types.split(',') if t.strip()}
        warnings = []
        target_key = target.key
        target_label = self.full_id_by_key.get(target_key, str(target_key))
        internal_members = []
        frontier_symbols = set()
        frontier_functions = set()
        target_files = set()

        if target_key[0] == 'File':
            target_files.add(target_key)
            for rel, child in self.out_edges.get(target_key, []):
                if rel == 'defines' and child[0] in {'Class', 'Function'}:
                    internal_members.append((child, 'defines', f"{target_label} -> defines -> {self.full_id_by_key.get(child, child)}"))
                    frontier_symbols.add(child)
                    if child[0] == 'Function':
                        frontier_functions.add(child)
                    if child[0] == 'Class':
                        for rel2, method in self.out_edges.get(child, []):
                            if rel2 == 'defines' and method[0] == 'Function':
                                internal_members.append((method, 'class method', f"{target_label} -> defines -> {self.full_id_by_key.get(child, child)} -> defines -> {self.full_id_by_key.get(method, method)}"))
                                frontier_symbols.add(method)
                                frontier_functions.add(method)
        elif target_key[0] == 'Class':
            frontier_symbols.add(target_key)
            for rel, method in self.out_edges.get(target_key, []):
                if rel == 'defines' and method[0] == 'Function':
                    internal_members.append((method, 'class method', f"{target_label} -> defines -> {self.full_id_by_key.get(method, method)}"))
                    frontier_symbols.add(method)
                    frontier_functions.add(method)
            for rel, parent in self.in_edges.get(target_key, []):
                if rel == 'defines' and parent[0] == 'File':
                    target_files.add(parent)
        elif target_key[0] == 'Function':
            frontier_symbols.add(target_key)
            frontier_functions.add(target_key)
            for rel, parent in self.in_edges.get(target_key, []):
                if rel == 'defines' and parent[0] == 'File':
                    target_files.add(parent)
                elif rel == 'defines' and parent[0] == 'Class':
                    for rel2, file_key in self.in_edges.get(parent, []):
                        if rel2 == 'defines' and file_key[0] == 'File':
                            target_files.add(file_key)

        deduped_internal_members = []
        seen_internal = set()
        for key, relation, path in internal_members:
            marker = (key, relation, path)
            if marker not in seen_internal:
                seen_internal.add(marker)
                deduped_internal_members.append((key, relation, path))

        scores = defaultdict(lambda: {'score': 0.0, 'tiers': [], 'relations': [], 'paths': []})
        for symbol in frontier_symbols:
            symbol_label = self.full_id_by_key.get(symbol, str(symbol))
            for rel, user in self.in_edges.get(symbol, []):
                if rel in {'imports', 'uses', 'instantiates', 'inherits', 'calls'} and user not in frontier_symbols:
                    weight = {'imports': 0.70, 'uses': 1.00, 'instantiates': 1.10, 'inherits': 1.05, 'calls': 0.85}.get(rel, 0.6)
                    direct_relation = {'imports': 'direct import', 'uses': 'direct class use', 'instantiates': 'direct instantiation', 'inherits': 'direct inheritance', 'calls': 'direct call'}.get(rel, rel)
                    self._add_score(scores, target_key, user, weight, 'Direct', direct_relation, f"{self.full_id_by_key.get(user, user)} -> {rel} -> {symbol_label}")
                    if user[0] == 'Function':
                        for rel2, container in self.in_edges.get(user, []):
                            if rel2 == 'defines' and container[0] in {'File', 'Class'}:
                                self._add_score(scores, target_key, container, weight * 0.65, 'Context', f"contains {direct_relation}", f"{self.full_id_by_key.get(container, container)} -> defines -> {self.full_id_by_key.get(user, user)} -> {rel} -> {symbol_label}")

        for func in list(frontier_functions):
            func_label = self.full_id_by_key.get(func, str(func))
            for rel, caller in self.in_edges.get(func, []):
                if rel == 'calls' and caller not in frontier_symbols:
                    self._add_score(scores, target_key, caller, 0.85, 'Direct', 'direct caller', f"{self.full_id_by_key.get(caller, caller)} -> calls -> {func_label}")
            for rel, callee in self.out_edges.get(func, []):
                if rel in {'calls', 'uses', 'instantiates'} and callee not in frontier_symbols:
                    weight = {'calls': 0.70, 'uses': 0.65, 'instantiates': 0.75}.get(rel, 0.60)
                    self._add_score(scores, target_key, callee, weight, 'Direct', f'direct {rel}', f"{func_label} -> {rel} -> {self.full_id_by_key.get(callee, callee)}")

        commits_touching_target = set()
        for file_key in target_files:
            for rel, commit_key in self.in_edges.get(file_key, []):
                if rel == 'modifies' and commit_key[0] == 'Commit':
                    commits_touching_target.add(commit_key)
        cochange_counts = defaultdict(int)
        for commit_key in commits_touching_target:
            for rel, file_key in self.out_edges.get(commit_key, []):
                if rel == 'modifies' and file_key[0] == 'File' and file_key not in target_files:
                    cochange_counts[file_key] += 1
        for file_key, count in cochange_counts.items():
            amount = min(0.60, 0.20 + 0.08 * count)
            self._add_score(scores, target_key, file_key, amount, 'Historical', 'git co-change', f"{target_label} <- co-change x{count} -> {self.full_id_by_key.get(file_key, file_key)}")

        gnn_scores = {}
        if mode in {'hybrid', 'gnn'}:
            if not os.path.exists(self.model_path):
                warnings.append(f"{mode} mode requested but model.pt is missing; falling back to deterministic scores.")
                mode = 'deterministic'
            else:
                try:
                    gnn_scores = self._compute_gnn_scores(target_key, gnn_type_filter, status_callback)
                except Exception as e:
                    warnings.append(f"GNN scoring failed: {e}. Falling back to deterministic scores.")
                    mode = 'deterministic'
                    gnn_scores = {}

        if mode in {'hybrid', 'gnn'} and gnn_scores:
            for key, gnn_score in sorted(gnn_scores.items(), key=lambda x: x[1], reverse=True)[:20]:
                if key not in scores:
                    scores[key]['score'] = 0.0
                    scores[key]['tiers'].append('GNN-suggested')
                    scores[key]['relations'].append('embedding proximity')
                    scores[key]['paths'].append('No direct deterministic path; suggested by GNN embedding proximity.')
                scores[key]['gnn_score'] = max(scores[key].get('gnn_score', 0.0), gnn_score)

        if mode == 'gnn':
            for key, info in scores.items():
                gnn_score = float(info.get('gnn_score', gnn_scores.get(key, 0.0)))
                info['rule_score'] = min(1.0, info['score'])
                info['gnn_score'] = gnn_score
                info['final_score'] = gnn_score
                if 'GNN-suggested' not in info['tiers']:
                    info['tiers'].append('GNN-suggested')
        elif mode == 'hybrid':
            for key, info in scores.items():
                rule_score = min(1.0, info['score'])
                gnn_score = float(info.get('gnn_score', gnn_scores.get(key, 0.0)))
                final_score = (0.85 * rule_score) + (0.15 * gnn_score) if rule_score > 0 else 0.20 * gnn_score
                info['rule_score'] = rule_score
                info['gnn_score'] = gnn_score
                info['final_score'] = min(1.0, final_score)
        else:
            for key, info in scores.items():
                info['rule_score'] = min(1.0, info['score'])
                info['gnn_score'] = 0.0
                info['final_score'] = info['rule_score']

        tier_priority = {'Direct': 0, 'Context': 1, 'Historical': 2, 'GNN-suggested': 3}
        ranked = sorted(scores.items(), key=lambda x: x[1]['final_score'], reverse=True)[:limit]
        candidates = []
        direct_count = 0
        for key, info in ranked:
            tiers = list(dict.fromkeys(info['tiers']))
            tiers = sorted(tiers, key=lambda t: tier_priority.get(t, 99))
            if any(t in {'Direct', 'Context'} for t in tiers):
                direct_count += 1
            candidates.append(ImpactCandidate(
                key=key,
                label=self.display_node_label(key),
                node_type=key[0],
                final_score=info['final_score'],
                rule_score=info['rule_score'],
                gnn_score=info['gnn_score'],
                tiers=tiers,
                relations=list(dict.fromkeys(info['relations'][:3])),
                paths=info['paths'],
            ))
        return ImpactResult(target, deduped_internal_members, candidates, mode, gnn_type_filter, direct_count, warnings)

    def _compute_gnn_scores(self, target_key, gnn_type_filter, status_callback=None):
        import torch
        import torch.nn.functional as F
        import torch_geometric.transforms as T
        from proven.core.ai.gnn_architecture import HGTLinkPrediction
        from proven.core.ai.predicter import Predictor

        def run():
            data_for_gnn = T.ToUndirected()(self.data)
            model = HGTLinkPrediction(128, 128, data=data_for_gnn, dropout=0.0)
            model.load_state_dict(torch.load(self.model_path, map_location='cpu', weights_only=True))
            predictor = Predictor(model, data=data_for_gnn)
            target_emb = predictor.embeddings.get(target_key[0])
            gnn_scores = {}
            if target_emb is not None and target_key[1] < target_emb.size(0):
                target_vec = target_emb[target_key[1]].view(1, -1)
                raw_gnn_scores = []
                for candidate_key in self.row_by_key.keys():
                    if not self._gnn_candidate_allowed(candidate_key, target_key, gnn_type_filter):
                        continue
                    cand_emb = predictor.embeddings.get(candidate_key[0])
                    if cand_emb is None or candidate_key[1] >= cand_emb.size(0):
                        continue
                    sim = F.cosine_similarity(target_vec, cand_emb[candidate_key[1]].view(1, -1), dim=1).item()
                    raw_gnn_scores.append((candidate_key, float(sim)))
                raw_gnn_scores.sort(key=lambda x: x[1], reverse=True)
                total_gnn = max(len(raw_gnn_scores) - 1, 1)
                for rank_idx, (candidate_key, _raw_score) in enumerate(raw_gnn_scores):
                    percentile_score = 1.0 - (rank_idx / total_gnn)
                    gnn_scores[candidate_key] = max(0.0, percentile_score)
            return gnn_scores

        if status_callback:
            return status_callback(run)
        return run()

    def _gnn_candidate_allowed(self, key, target_key, gnn_type_filter):
        if key == target_key or key[0] not in gnn_type_filter or not self.is_project_candidate(key):
            return False
        if key[0] in {'File', 'Class'}:
            return True
        if key[0] == 'Function':
            row = self.row_by_key.get(key)
            if row is None:
                return False
            return str(row.get('kind', '')).lower() == 'project' or key in self.project_defined_functions
        return False

