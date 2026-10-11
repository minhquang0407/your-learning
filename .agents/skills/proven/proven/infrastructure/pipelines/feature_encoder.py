import os
import hashlib
import numpy as np

try:
    import torch
except ImportError:
    torch = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

class CodebaseFeatureEncoder:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.device = 'cuda' if torch is not None and torch.cuda.is_available() else 'cpu'
        self.feature_dim = 384
        print(f"Loading Feature Encoder ({model_name}) on {self.device}...")
        self.model = None
        if SentenceTransformer is not None:
            try:
                self.model = SentenceTransformer(model_name, device=self.device)
            except Exception as e:
                print(f"WARNING: Could not load sentence-transformers model: {e}")
                print("WARNING: Falling back to deterministic hash embeddings.")
        else:
            print("WARNING: sentence-transformers not installed. Using deterministic hash embeddings.")

    def _build_text(self, node_id, node_data):
        node_type = node_data.get('type', 'Unknown')
        name = node_data.get('name', str(node_id))

        if node_type == 'File':
            functions = node_data.get('functions', []) or []
            classes = node_data.get('classes', []) or []
            symbol_text = ' '.join(functions[:40] + classes[:20])
            # Use actual code symbols only. Do not inject generic concepts into every file,
            # otherwise __init__/config files look falsely related to all bug reports.
            return f"File path: {name}. Source code symbols: {symbol_text}"

        if node_type == 'Function':
            kind = node_data.get('kind', 'unknown')
            defined_in = node_data.get('defined_in')
            module = node_data.get('module')
            if kind == 'project':
                return (
                    f"Project-defined function {name}. Defined in {defined_in}. "
                    f"Code operation or behavior: {name.replace('_', ' ')}"
                )
            if kind == 'builtin':
                return f"Python builtin helper function {name}. Common utility with low domain-specific impact."
            if kind == 'external':
                return f"External library API function {name}. Module: {module}. Library call or framework API."
            return f"Unresolved function {name}. Code operation or behavior: {name.replace('_', ' ')}"

        if node_type == 'Class':
            return f"Class named {name}. Object or component: {name.replace('_', ' ')}"

        if node_type == 'Commit':
            return f"Commit change description {name}"

        if node_type == 'Developer':
            return f"Developer {name}"

        return f"{node_type} named {name}"

    def encode_nodes(self, graph):
        """Iterate over graph nodes and use embedder to encode node names/semantics into vectors."""
        print(f"Encoding {graph.number_of_nodes()} nodes...")
        texts = []
        node_ids = list(graph.nodes())
        
        for n in node_ids:
            node_data = graph.nodes[n]
            texts.append(self._build_text(n, node_data))

        if self.model is not None:
            try:
                # Encode in batches for speed
                embeddings = self.model.encode(texts, batch_size=256, show_progress_bar=True, convert_to_numpy=True)
            except Exception as e:
                print(f"WARNING: Feature model encode failed: {e}")
                print("WARNING: Falling back to deterministic hash embeddings.")
                embeddings = self._hash_embeddings(texts)
        else:
            embeddings = self._hash_embeddings(texts)

        # Map back to graph
        for i, n in enumerate(node_ids):
            graph.nodes[n]['feature'] = embeddings[i]

        print("Feature encoding completed.")
        return graph

    def _hash_embeddings(self, texts):
        embeddings = np.zeros((len(texts), self.feature_dim), dtype=np.float32)
        for row_idx, text in enumerate(texts):
            for token in text.lower().replace('/', ' ').replace('.', ' ').replace('_', ' ').split():
                digest = hashlib.blake2b(token.encode('utf-8'), digest_size=8).digest()
                value = int.from_bytes(digest, byteorder='little', signed=False)
                col = value % self.feature_dim
                sign = 1.0 if (value >> 63) == 0 else -1.0
                embeddings[row_idx, col] += sign
            norm = np.linalg.norm(embeddings[row_idx])
            if norm > 0:
                embeddings[row_idx] /= norm
        return embeddings
