import os
import re
from typing import Dict, Any, List

from softgnn_advisor.config.settings import get_project_paths
from softgnn_advisor.core.metadata_utils import load_metadata
from softgnn_advisor.core.developer_aliases import load_developer_aliases, resolve_developer_identity
from softgnn_advisor.core.file_filters import is_source_code_file, is_valid_developer_name


class TriageEngine:
    """Hybrid Bug Triage & Reviewer Recommendation Engine.
    
    Combines:
    1. GNN Link Prediction embedding similarity (Developer <-> Bug vector).
    2. Git commit authorship and file ownership (Developer -> Commit -> File).
    3. Semantic and lexical bug-to-file relevance.
    """

    def __init__(self, project: str, repo_path: str = None):
        self.project = project
        self.repo_path = os.path.abspath(repo_path or os.getcwd())
        self.paths = get_project_paths(project)

    def triage(self, bug_description: str, max_devs: int = 3, max_files: int = 5) -> Dict[str, Any]:
        """Perform hybrid triage matching for a bug description or PR change description."""
        try:
            import torch
            import torch.nn.functional as F
            import torch_geometric.transforms as T
            import pandas as pd
            from softgnn_advisor.core.ai.predicter import Predictor
            from softgnn_advisor.core.ai.gnn_architecture import HGTLinkPrediction
            from softgnn_advisor.infrastructure.pipelines.feature_encoder import CodebaseFeatureEncoder
        except ImportError as exc:
            return {
                "status": "error",
                "error_type": "MISSING_DEPENDENCY",
                "message": f"Triage requires GNN dependencies: {exc}. Install with `pip install softgnn-advisor[gnn]`.",
                "top_engineers": [],
                "related_files": [],
            }

        pyg_data_path = self.paths['PYG_DATA_PATH']
        model_path = self.paths['MODEL_PATH']
        nodes_data_path = self.paths['NODES_DATA_PATH']
        metadata_path = self.paths['METADATA_PATH']

        if not os.path.exists(model_path) or not os.path.exists(pyg_data_path) or not os.path.exists(nodes_data_path):
            return {
                "status": "error",
                "error_type": "MODEL_NOT_FOUND",
                "message": f"Trained model or graph data not found for project '{self.project}'. Please run `softgnn train --project {self.project}` first.",
                "top_engineers": [],
                "related_files": [],
            }

        metadata = load_metadata(metadata_path)
        source_path = metadata.get('source_path') or self.repo_path
        developer_aliases = load_developer_aliases(self.paths['DEVELOPER_ALIASES_PATH'])

        # 1. Encode bug description
        try:
            encoder = CodebaseFeatureEncoder()
            bug_vec = encoder.model.encode([bug_description], convert_to_numpy=True)[0]
        except Exception as exc:
            return {
                "status": "error",
                "error_type": "ENCODING_FAILED",
                "message": f"Failed to encode bug description: {exc}",
                "top_engineers": [],
                "related_files": [],
            }

        # 2. Load graph + model
        data = torch.load(pyg_data_path, map_location='cpu', weights_only=False)
        data = T.ToUndirected()(data)

        model = HGTLinkPrediction(128, 128, data=data, dropout=0.0)
        model.load_state_dict(torch.load(model_path, map_location='cpu', weights_only=True))

        predictor = Predictor(model, data=data)
        device = predictor.device

        # 3. Project bug vector
        bug_tensor = torch.tensor(bug_vec, dtype=torch.float32).unsqueeze(0).to(device)
        with torch.no_grad():
            projected_bug = predictor.model.encoder.lin_dict['Commit'](bug_tensor).relu_()

        # 4. Score Developer nodes (GNN)
        df = pd.read_csv(nodes_data_path)
        dev_df = df[df['type'] == 'Developer'].copy()

        if dev_df.empty or 'Developer' not in predictor.embeddings:
            return {
                "status": "warning",
                "message": "No Developer nodes found in the graph.",
                "top_engineers": [],
                "related_files": [],
            }

        dev_embeddings = predictor.embeddings['Developer'].to(device)
        decoder_key = '__authored_by__'
        if decoder_key not in predictor.model.decoders:
            decoder_key = list(predictor.model.decoders.keys())[0]
        decoder = predictor.model.decoders[decoder_key]

        batch_src = projected_bug.expand(dev_embeddings.size(0), -1)
        with torch.no_grad():
            logits = decoder(batch_src, dev_embeddings)
            gnn_scores = torch.sigmoid(logits).view(-1).detach().cpu().numpy()

        # 5. Lexical relevance
        def lexical_file_relevance(rel_path: str) -> float:
            if not source_path:
                return 0.0
            full_path = os.path.join(source_path, rel_path.replace('/', os.sep))
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read(20000).lower()
            except Exception:
                return 0.0

            bug_text = bug_description.lower()
            bug_terms = set(re.findall(r"[a-zA-Z_]+", bug_text))
            file_loading_intent = any(term in bug_text for term in ['file', 'load', 'loading', 'read', 'upload', 'download'])
            if file_loading_intent:
                terms = [
                    'open(', 'read(', 'read_csv', 'read_excel', 'json.load', 'yaml.safe_load',
                    'upload', 'download', 'load', 'loads', 'parse', 'extract', 'path', 'filepath', 'filename', 'csv', 'json'
                ]
            else:
                terms = list(bug_terms)

            hits = sum(1 for term in terms if term and term in text)
            path_bonus = sum(1 for term in terms if term and term.replace('(', '') in rel_path.lower())
            return min(1.0, (hits + path_bonus) / 8.0)

        # 6. Semantic bug -> File matching
        file_df = df[df['type'] == 'File'].copy()
        file_df['rel_path'] = file_df['id'].astype(str).str.replace('FILE:', '', regex=False)
        file_df = file_df[file_df['rel_path'].apply(is_source_code_file)]
        if source_path:
            file_df = file_df[file_df['rel_path'].apply(lambda p: os.path.exists(os.path.join(source_path, p.replace('/', os.sep))))]

        file_semantic_scores = {}
        top_related_files = []
        if 'File' in data.node_types and not file_df.empty:
            file_x = data['File'].x.float()
            bug_feature = torch.tensor(bug_vec, dtype=torch.float32).view(1, -1)
            if file_x.size(1) == bug_feature.size(1):
                sims = F.cosine_similarity(file_x, bug_feature.expand(file_x.size(0), -1), dim=1)
                for _, row in file_df.iterrows():
                    pyg_id = int(row['pyg_id'])
                    if pyg_id < len(sims):
                        file_id = str(row['id']).replace('FILE:', '')
                        semantic_score = float((sims[pyg_id].item() + 1.0) / 2.0)
                        lexical_score = lexical_file_relevance(file_id)
                        combined_score = (0.65 * semantic_score) + (0.35 * lexical_score)
                        file_semantic_scores[pyg_id] = combined_score
                        top_related_files.append((file_id, combined_score, semantic_score, lexical_score, pyg_id))
                top_related_files.sort(key=lambda x: x[1], reverse=True)
                top_related_files = top_related_files[:max_files]

        # 7. Git ownership: Developer -> Commit -> File
        commit_to_devs = {}
        if ('Developer', 'authored_by', 'Commit') in data.edge_types:
            for src, dst in data[('Developer', 'authored_by', 'Commit')].edge_index.t().tolist():
                commit_to_devs[int(dst)] = int(src)

        dev_ownership_raw = {}
        dev_direct_evidence = {}
        dev_broad_evidence = {}
        if ('Commit', 'modifies', 'File') in data.edge_types:
            related_file_ids = {pyg_id for _, _, _, _, pyg_id in top_related_files}
            file_name_by_pyg = {
                int(row['pyg_id']): str(row['id']).replace('FILE:', '')
                for _, row in file_df.iterrows()
            }
            for commit_id, file_id in data[('Commit', 'modifies', 'File')].edge_index.t().tolist():
                commit_id = int(commit_id)
                file_id = int(file_id)
                dev_id = commit_to_devs.get(commit_id)
                if dev_id is None:
                    continue

                sem = file_semantic_scores.get(file_id, 0.0)
                is_direct = file_id in related_file_ids
                contribution = sem if is_direct else sem * 0.10
                dev_ownership_raw[dev_id] = dev_ownership_raw.get(dev_id, 0.0) + max(contribution, 0.001)

                fname = file_name_by_pyg.get(file_id)
                if fname:
                    target = dev_direct_evidence if is_direct else dev_broad_evidence
                    target.setdefault(dev_id, {})[fname] = target.setdefault(dev_id, {}).get(fname, 0) + 1

        max_ownership = max(dev_ownership_raw.values()) if dev_ownership_raw else 1.0

        W_GNN = 0.45
        W_GIT = 0.35
        W_SEM = 0.20

        best_by_name = {}
        for _, row in dev_df.iterrows():
            dev_pyg_id = int(row['pyg_id'])
            dev_name = resolve_developer_identity(str(row['name']), '', developer_aliases)
            if not is_valid_developer_name(dev_name):
                continue
            gnn_score = float(gnn_scores[dev_pyg_id]) if dev_pyg_id < len(gnn_scores) else 0.0
            git_score = float(dev_ownership_raw.get(dev_pyg_id, 0.0) / max_ownership) if max_ownership else 0.0
            direct_evidence = dev_direct_evidence.get(dev_pyg_id, {})
            broad_evidence = dev_broad_evidence.get(dev_pyg_id, {})

            sem_score = 0.0
            if direct_evidence and top_related_files:
                touched_related = set(direct_evidence.keys())
                top_file_names = {name for name, _, _, _, _ in top_related_files}
                sem_score = len(touched_related & top_file_names) / max(len(top_file_names), 1)

            final_score = (W_GNN * gnn_score) + (W_GIT * git_score) + (W_SEM * sem_score)
            current = best_by_name.get(dev_name)
            if current is None or final_score > current['final_score']:
                best_by_name[dev_name] = {
                    'final_score': final_score,
                    'gnn_score': gnn_score,
                    'git_score': git_score,
                    'sem_score': sem_score,
                    'direct_evidence': direct_evidence,
                    'broad_evidence': broad_evidence,
                }

        ranked = sorted(best_by_name.items(), key=lambda x: x[1]['final_score'], reverse=True)

        engineers_out = []
        for rank, (dev_name, info) in enumerate(ranked[:max_devs], start=1):
            evidence_source = info['direct_evidence'] or info['broad_evidence']
            evidence_items = sorted(evidence_source.items(), key=lambda x: x[1], reverse=True)[:3]
            prefix = "Direct: " if info['direct_evidence'] else "Broad: "
            evidence_str = (prefix + ", ".join(f"{f} ({c})" for f, c in evidence_items)) if evidence_items else "No direct commits"

            engineers_out.append({
                "rank": rank,
                "developer": dev_name,
                "final_score": round(info['final_score'], 4),
                "gnn_score": round(info['gnn_score'], 4),
                "git_score": round(info['git_score'], 4),
                "sem_score": round(info['sem_score'], 4),
                "evidence": evidence_str,
            })

        files_out = []
        for idx, (fname, relevance, semantic_score, lexical_score, _) in enumerate(top_related_files, start=1):
            files_out.append({
                "rank": idx,
                "file": fname,
                "relevance": round(relevance, 4),
                "semantic_score": round(semantic_score, 4),
                "lexical_score": round(lexical_score, 4),
            })

        return {
            "status": "success",
            "project": self.project,
            "query": bug_description,
            "top_engineers": engineers_out,
            "related_files": files_out,
        }
