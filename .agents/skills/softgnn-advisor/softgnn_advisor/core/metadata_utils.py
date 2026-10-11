import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_metadata(path) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_metadata(path, data: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)


def compute_graph_schema_hash(data) -> str:
    """Hash schema shape, not individual edge values.

    This detects model/graph architecture mismatch caused by changed node types,
    edge types, or feature dimensions.
    """
    payload = {
        'node_types': sorted(list(data.node_types)),
        'edge_types': sorted([list(et) for et in data.edge_types]),
        'feature_dims': {
            ntype: int(data[ntype].x.size(1)) if hasattr(data[ntype], 'x') else 0
            for ntype in data.node_types
        },
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def summarize_heterodata(data) -> Dict[str, Any]:
    node_counts = {
        ntype: int(data[ntype].num_nodes)
        for ntype in data.node_types
    }
    edge_counts = {
        ' | '.join(et): int(data[et].edge_index.size(1))
        for et in data.edge_types
    }
    return {
        'node_count': int(data.num_nodes),
        'edge_count': int(data.num_edges),
        'node_types': list(data.node_types),
        'edge_types': [' | '.join(et) for et in data.edge_types],
        'node_counts': node_counts,
        'edge_counts': edge_counts,
        'schema_hash': compute_graph_schema_hash(data),
    }
