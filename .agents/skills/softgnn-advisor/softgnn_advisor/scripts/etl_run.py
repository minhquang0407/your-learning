import os
import sys
import pickle
import networkx as nx
import pandas as pd

try:
    import torch
    from torch_geometric.data import HeteroData
    HAS_GNN_DEPS = True
except ImportError:
    torch = None
    HeteroData = None
    HAS_GNN_DEPS = False

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from softgnn_advisor.infrastructure.pipelines.ast_parser import CodebaseASTParser
from softgnn_advisor.infrastructure.pipelines.git_parser import CodebaseGitParser
from softgnn_advisor.infrastructure.pipelines.feature_encoder import CodebaseFeatureEncoder
from softgnn_advisor.infrastructure.pipelines.contract_extractor import ContractExtractor, load_contract_snapshot, save_contract_snapshot
from softgnn_advisor.infrastructure.pipelines.test_parser import TestGraphParser
from softgnn_advisor.config.settings import get_project_paths
from softgnn_advisor.core.metadata_utils import load_metadata, save_metadata, summarize_heterodata, utc_now_iso
from softgnn_advisor.core.developer_aliases import load_developer_aliases

def run_etl_pipeline(target_repo_path, project_name):
    paths = get_project_paths(project_name)
    GRAPH_PATH = paths['GRAPH_PATH']
    PYG_DATA_PATH = paths['PYG_DATA_PATH']
    NODES_DATA_PATH = paths['NODES_DATA_PATH']
    METADATA_PATH = paths['METADATA_PATH']
    DEVELOPER_ALIASES_PATH = paths['DEVELOPER_ALIASES_PATH']
    CONTRACTS_PATH = paths['CONTRACTS_PATH']
    TEST_COVERAGE_EDGES_PATH = paths['TEST_COVERAGE_EDGES_PATH']
    
    print(f"=== 1. Parsing AST from {target_repo_path} ===")
    ast_parser = CodebaseASTParser(target_repo_path)
    ast_graph = ast_parser.parse_all()

    print(f"=== 2. Extracting Function Contracts from {target_repo_path} ===")
    contract_extractor = ContractExtractor(target_repo_path)
    previous_contracts = load_contract_snapshot(str(CONTRACTS_PATH))
    current_contracts = contract_extractor.extract_all()
    contract_graph, contract_snapshot = contract_extractor.build_graph_and_snapshot(current_contracts, previous_contracts)
    save_contract_snapshot(str(CONTRACTS_PATH), contract_snapshot)
    print(f"Extracted {contract_graph.number_of_nodes()} contract nodes and {contract_graph.number_of_edges()} contract edges.")

    print(f"=== 3. Parsing Test Graph from {target_repo_path} ===")
    test_parser = TestGraphParser(target_repo_path, project_symbols=ast_parser.project_symbols, contract_snapshot=contract_snapshot)
    test_graph, test_evidence = test_parser.parse_all()
    with open(str(TEST_COVERAGE_EDGES_PATH), 'w', encoding='utf-8') as f:
        import json
        json.dump(test_evidence, f, indent=2)
    print(f"Extracted {test_graph.number_of_nodes()} test nodes and {test_graph.number_of_edges()} test edges.")
    
    print(f"=== 4. Parsing Git History from {target_repo_path} ===")
    developer_aliases = load_developer_aliases(DEVELOPER_ALIASES_PATH)
    if developer_aliases:
        print(f"Loaded {len(developer_aliases)} developer aliases.")
    git_parser = CodebaseGitParser(target_repo_path, developer_aliases=developer_aliases)
    git_graph = git_parser.parse_all()
    
    print("=== 5. Merging Graphs ===")
    G = nx.compose_all([ast_graph, contract_graph, test_graph, git_graph])
    print(f"Merged Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.")
    
    print("=== 6. Encoding Text Features (LLM Embeddings) ===")
    encoder = CodebaseFeatureEncoder()
    G = encoder.encode_nodes(G)
    
    print("=== 7. Saving Raw NetworkX Graph ===")
    with open(str(GRAPH_PATH), 'wb') as f:
        pickle.dump(G, f, pickle.HIGHEST_PROTOCOL)
    
    if HAS_GNN_DEPS:
        print("=== 8. Converting to PyTorch Geometric HeteroData ===")
        hetero_data, node_mapping = convert_nx_to_pyg(G)
        torch.save(hetero_data, str(PYG_DATA_PATH))
        graph_summary = summarize_heterodata(hetero_data)
    else:
        print("=== 8. Skipping PyTorch Geometric export (install softgnn-advisor[gnn] to enable GNN training/ranking) ===")
        node_mapping = build_node_mapping(G)
        graph_summary = summarize_networkx_graph(G)

    metadata = load_metadata(METADATA_PATH)
    metadata.update({
        'project': project_name,
        'source_path': os.path.abspath(target_repo_path),
        'etl_finished_at': utc_now_iso(),
        'gnn_artifacts_available': HAS_GNN_DEPS,
        **graph_summary,
    })
    save_metadata(METADATA_PATH, metadata)
    print(f"Metadata saved to {METADATA_PATH}")
    
    nodes_data = []
    for ntype, mapping in node_mapping.items():
        for n, pyg_id in mapping.items():
            d = G.nodes[n]
            row = {
                'id': n,
                'type': ntype,
                'name': d.get('name', str(n)),
                'pyg_id': pyg_id,
            }
            for key in ('kind', 'is_project_defined', 'defined_in', 'module'):
                value = d.get(key)
                if isinstance(value, (str, int, float, bool)) or value is None:
                    row[key] = value
            nodes_data.append(row)
    df = pd.DataFrame(nodes_data)
    df.to_csv(str(NODES_DATA_PATH), index=False)
    
    print("ETL Pipeline Completed Successfully!")

def build_node_mapping(G):
    node_mapping = {}
    for n, d in G.nodes(data=True):
        ntype = d.get('type', 'Unknown')
        if ntype not in node_mapping:
            node_mapping[ntype] = {}
        node_mapping[ntype][n] = len(node_mapping[ntype])
    return node_mapping


def summarize_networkx_graph(G):
    node_counts = {}
    edge_counts = {}
    for _, d in G.nodes(data=True):
        ntype = d.get('type', 'Unknown')
        node_counts[ntype] = node_counts.get(ntype, 0) + 1
    for u, v, d in G.edges(data=True):
        src_t = G.nodes[u].get('type', 'Unknown')
        dst_t = G.nodes[v].get('type', 'Unknown')
        rel = d.get('type', 'linked')
        edge_key = f"{src_t} | {rel} | {dst_t}"
        edge_counts[edge_key] = edge_counts.get(edge_key, 0) + 1
    return {
        'node_count': G.number_of_nodes(),
        'edge_count': G.number_of_edges(),
        'node_types': sorted(node_counts.keys()),
        'edge_types': sorted(edge_counts.keys()),
        'node_counts': node_counts,
        'edge_counts': edge_counts,
        'schema_hash': None,
    }


def convert_nx_to_pyg(G):
    data = HeteroData()
    node_mapping = {}
    
    # 1. Map nodes by type
    for n, d in G.nodes(data=True):
        ntype = d.get('type', 'Unknown')
        if ntype not in node_mapping:
            node_mapping[ntype] = {}
        
        node_mapping[ntype][n] = len(node_mapping[ntype])
        
    # 2. Extract features
    for ntype, mapping in node_mapping.items():
        num_nodes = len(mapping)
        feature_dim = 384 # default
        for n in mapping:
            feat = G.nodes[n].get('feature')
            if feat is not None:
                feature_dim = len(feat)
                break
                
        features = torch.zeros((num_nodes, feature_dim), dtype=torch.float32)
        for n, idx in mapping.items():
            feat = G.nodes[n].get('feature')
            if feat is not None:
                features[idx] = torch.tensor(feat, dtype=torch.float32)
                
        data[ntype].x = features
        
    # 3. Extract edges
    edge_dict = {}
    for u, v, k, d in G.edges(data=True, keys=True):
        rel = d.get('type', 'linked')
        u_type = G.nodes[u].get('type', 'Unknown')
        v_type = G.nodes[v].get('type', 'Unknown')
        
        edge_type = (u_type, rel, v_type)
        if edge_type not in edge_dict:
            edge_dict[edge_type] = {'src': [], 'dst': []}
            
        u_idx = node_mapping[u_type][u]
        v_idx = node_mapping[v_type][v]
        
        edge_dict[edge_type]['src'].append(u_idx)
        edge_dict[edge_type]['dst'].append(v_idx)
        
    for edge_type, indices in edge_dict.items():
        src = torch.tensor(indices['src'], dtype=torch.long)
        dst = torch.tensor(indices['dst'], dtype=torch.long)
        data[edge_type].edge_index = torch.stack([src, dst], dim=0)
        
    return data, node_mapping

if __name__ == '__main__':
    # Analyze the project's own source code
    target_project = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    run_etl_pipeline(target_project)
