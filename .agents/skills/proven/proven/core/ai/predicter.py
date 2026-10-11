import os
import torch
import torch.nn.functional as F
import torch.amp
from proven.infrastructure.repositories import PyGDataRepository
from proven.core.interfaces import ILinkPredictor


class Predictor(ILinkPredictor):
    def __init__(self, model, data=None, metadata=None, embeddings=None):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = model

        # Handle metadata
        if data is not None:
            self.data = data
            self.metadata = data.metadata()
        elif metadata is not None:
            self.metadata = metadata

        self.model.eval()
        self.model.to(self.device)

        if embeddings is not None:
            self.embeddings = embeddings
        else:
            if data is not None:
                self.embeddings = self._compute_all_embeddings()
            else:
                raise ValueError("Predictor needs either 'embeddings' or 'data' to work!")

        # Compute degree for hub penalty
        if data is not None:
            self.node_degrees = self._compute_node_degrees(data)
        else:
            self.node_degrees = {}

        self.connectivity_map = self._build_connectivity_map()
        # Codebase semantic rules
        self.DEV_RELS = {'authored_by', 'modifies'}
        self.CODE_RELS = {'calls', 'defines'}

    def _compute_node_degrees(self, data):
        """Compute degree for all nodes to apply hub penalty."""
        print("Computing Node Degrees for Hub Penalty...")
        degrees_map = {}
        for node_type in data.node_types:
            num_nodes = data[node_type].num_nodes
            if num_nodes == 0: continue

            # Initialize zero vector
            d = torch.zeros(num_nodes, dtype=torch.float)

            # Iterate over incoming edges to this node_type
            for src, rel, dst in data.edge_types:
                if dst == node_type:
                    edge_index = data[(src, rel, dst)].edge_index
                    # Count occurrence frequency of dst_index
                    dst_indices = edge_index[1].cpu()
                    d += torch.bincount(dst_indices, minlength=num_nodes).float()

            degrees_map[node_type] = d
        return degrees_map
    @torch.no_grad()
    def _compute_all_embeddings(self, batch_size=1024):
        """Compute and return embeddings using full-batch to avoid loader bottlenecks."""
        data = self.data
        embeddings = {}
        self.model.eval()
        print(f"[INFO] Computing Embeddings on {self.device} (Full-Batch)...")

        # Push data to device
        x_dict = {k: v.to(self.device) for k, v in data.x_dict.items()}
        edge_index_dict = {k: v.to(self.device) for k, v in data.edge_index_dict.items()}

        with torch.no_grad():
            with torch.amp.autocast('cuda') if self.device == 'cuda' else torch.amp.autocast('cpu', enabled=False):
                z_dict = self.model.encoder(x_dict, edge_index_dict)

        for node_type in data.node_types:
            if node_type in z_dict:
                raw_emb = z_dict[node_type].cpu()
                final_emb = F.normalize(raw_emb, p=2, dim=1)
                embeddings[node_type] = final_emb

        return embeddings

    @torch.no_grad()
    def _build_connectivity_map(self):
        # Use metadata edge_types from init
        node_types, edge_types = self.metadata
        mapping = {}
        for src, rel, dst in edge_types:
            if src not in mapping: mapping[src] = {}
            if dst not in mapping[src]: mapping[src][dst] = []
            mapping[src][dst].append(rel)
        return mapping

    def scan_relationship(self, id_a, id_b, src_type, dst_type, mode='strict'):
        """Scan relationship between two nodes.

        Args:
            mode (str):
                - 'strict': Only check relations in metadata schema.
                - 'loose': Check all relations learned by model (zero-shot transfer).
        """
        results = {}
        max_score = -1
        best_rel = None

        # 1. Determine candidate relations
        candidate_rels = set()

        if mode == 'strict':
            # Strict mode: only relations defined in schema
            candidate_rels = set(self.connectivity_map.get(src_type, {}).get(dst_type, []))
        else:
            # Loose mode (zero-shot): all relations learned by model
            for key in self.model.decoders.keys():
                rel_name = key.strip('_')
                if '__' in key.strip('_'): rel_name = key.split('__')[1]
                candidate_rels.add(rel_name)

        # 2. Iterate and predict
        for rel in candidate_rels:
            if rel.startswith('rev_'): continue

            # Rule 1: Git relations (Developer only)
            if rel in self.DEV_RELS:
                if src_type != 'Developer':
                    continue

            # Rule 2: Code relations (Class/Function/File)
            if rel in self.CODE_RELS:
                if src_type == 'Developer' or dst_type == 'Developer':
                    continue
            score = self._get_score_fast(id_a, id_b, src_type, rel, dst_type)

            if score > 0.001:
                results[rel] = score
                if score > max_score:
                    max_score = score
                    best_rel = rel

        return best_rel, max_score, results

    def _get_score_fast(self, src_id, dst_id, src_type, rel, dst_type):
        """Helper function to compute edge score."""
        if rel.startswith('rev_'): rel = rel.replace('rev_', '')

        # Matches decoder key format __rel__
        key = f"__{rel}__"

        if key not in self.model.decoders: return 0.0

        try:
            vec_a = self.embeddings[src_type][src_id].to(self.device).view(1, -1)
            vec_b = self.embeddings[dst_type][dst_id].to(self.device).view(1, -1)
            logits = self.model.decoders[key](vec_a, vec_b)
            return torch.sigmoid(logits).item()
        except:
            return 0.0

    @torch.no_grad()
    def recommend_top_k(self, src_id, top_k=10, src_type='human', dst_type=None, rel_name=None):
        """Unified recommendation query.

        Handles:
        1. Specific relation when rel_name is provided.
        2. Target node type when dst_type is provided (max-pooled over relations).
        3. Global search when neither is specified.
        """
        if src_type not in self.embeddings: return []

        try:
            vec_src = self.embeddings[src_type][src_id].view(1, -1).to(self.device)
        except IndexError:
            return []

        # 1. Build search plan
        search_plan = {}  # {dst_type: [rel1, rel2]}

        if rel_name:
            # Case 1: Search by specific relation
            node_types, edge_types = self.metadata
            for s, r, d in edge_types:
                if s == src_type and r == rel_name:
                    if dst_type is None or dst_type == d:
                        if d not in search_plan: search_plan[d] = []
                        search_plan[d].append(r)
        elif dst_type:
            # Case 2: Search by destination type
            rels = self.connectivity_map.get(src_type, {}).get(dst_type, [])
            if rels: search_plan[dst_type] = rels
        else:
            # Case 3: Global search
            search_plan = self.connectivity_map.get(src_type, {})

        global_candidates = []
        eval_batch_size = 4096

        # 2. Execute inference
        for target_type, rels in search_plan.items():
            if target_type not in self.embeddings: continue

            candidates_emb = self.embeddings[target_type]
            num_candidates = candidates_emb.size(0)

            # Tensor tracking max score per candidate
            best_scores = torch.full((num_candidates,), -1.0, device='cpu')
            best_rels = [None] * num_candidates

            for r_name in rels:
                if r_name.startswith('rev_'): continue

                key = f"__{r_name}__"
                if key not in self.model.decoders: continue
                decoder = self.model.decoders[key]

                # Batch Inference
                for i in range(0, num_candidates, eval_batch_size):
                    batch_dst = candidates_emb[i: i + eval_batch_size].to(self.device)
                    batch_src = vec_src.expand(batch_dst.size(0), -1)

                    with torch.no_grad():
                        with torch.amp.autocast(self.device) if self.device == 'cuda' else torch.amp.autocast('cpu', enabled=False):
                            logits = decoder(batch_src, batch_dst)
                            scores = torch.sigmoid(logits).view(-1).detach().cpu()
                        if hasattr(self, 'node_degrees') and target_type in self.node_degrees:
                            batch_indices = range(i, i + len(scores))
                            # Bounds check for degrees
                            if batch_indices[-1] < len(self.node_degrees[target_type]):
                                batch_degrees = self.node_degrees[target_type][batch_indices]
                                penalty = torch.log(batch_degrees + 1) + 1
                                scores = scores / penalty
                    # Update max score
                    current_slice = slice(i, i + len(scores))
                    mask = scores > best_scores[current_slice]
                    best_scores[current_slice] = torch.where(mask, scores, best_scores[current_slice])

                    indices = torch.nonzero(mask).flatten() + i
                    for idx in indices:
                        best_rels[idx.item()] = r_name

            if src_type == target_type:
                best_scores[src_id] = -1.0

            k_local = min(top_k, num_candidates)
            vals, indices = torch.topk(best_scores, k=k_local)

            for val, idx in zip(vals, indices):
                if val > 0.0:
                    idx = idx.item()
                    global_candidates.append({
                        'id': idx,
                        'type': target_type,
                        'relation': best_rels[idx],
                        'score': val.item()
                    })

        global_candidates.sort(key=lambda x: x['score'], reverse=True)
        return global_candidates[:top_k]
