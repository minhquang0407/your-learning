import torch
import torch.nn.functional as F
import torch_geometric.transforms as T
import numpy as np
from sklearn.metrics import roc_auc_score
import os

from softgnn_advisor.core.ai.gnn_architecture import HGTLinkPrediction
from softgnn_advisor.config.settings import get_project_paths
from softgnn_advisor.core.metadata_utils import compute_graph_schema_hash, load_metadata, save_metadata, utc_now_iso

def prepare_data(data_path):
    print("Loading PyG Data...")
    data = torch.load(data_path, map_location='cpu', weights_only=False)
    print(f"Original Graph: {data.num_nodes} nodes, {data.num_edges} edges.")
    
    print("Making graph undirected (creates reverse edges)...")
    data = T.ToUndirected()(data)
    
    target_edge_types = []
    rev_edge_types = []
    for edge_type in data.edge_types:
        src, rel, dst = edge_type
        if not rel.startswith('rev_'):
            if src == dst:
                target_edge_types.append(edge_type)
                rev_edge_types.append(edge_type)  # Self-loop is its own reverse
            else:
                rev_rel = f"rev_{rel}"
                if (dst, rev_rel, src) in data.edge_types:
                    target_edge_types.append(edge_type)
                    rev_edge_types.append((dst, rev_rel, src))
                
    print(f"Target edges for prediction: {len(target_edge_types)} types.")
    for et in target_edge_types:
        print(f"  - {et}")
    
    print("Splitting data into Train/Val/Test...")
    transform = T.RandomLinkSplit(
        num_val=0.1,
        num_test=0.1,
        is_undirected=True,
        edge_types=target_edge_types,
        rev_edge_types=rev_edge_types,
        disjoint_train_ratio=0.3,
        add_negative_train_samples=True 
    )
    
    train_data, val_data, test_data = transform(data)
    return train_data, val_data, test_data, target_edge_types

def train_epoch(model, train_data, target_edge_types, optimizer, device):
    model.train()
    optimizer.zero_grad()
    
    total_loss = 0
    total_examples = 0
    
    # Push data to device once (Full-Batch)
    x_dict = {k: v.to(device) for k, v in train_data.x_dict.items()}
    edge_index_dict = {k: v.to(device) for k, v in train_data.edge_index_dict.items()}
    
    for edge_type in target_edge_types:
        edge_label_index = train_data[edge_type].edge_label_index
        if edge_label_index.numel() == 0: continue
            
        edge_label_index = edge_label_index.to(device)
        edge_label = train_data[edge_type].edge_label.to(device)
        
        with torch.amp.autocast('cuda') if device.type == 'cuda' else torch.amp.autocast('cpu', enabled=False):
            out = model(x_dict, edge_index_dict, edge_type, edge_label_index)
            loss = F.binary_cross_entropy_with_logits(out, edge_label)
            
        loss.backward()
        
        total_loss += loss.item() * edge_label.size(0)
        total_examples += edge_label.size(0)
        
    optimizer.step()
    return total_loss / max(total_examples, 1)

@torch.no_grad()
def evaluate(model, data, target_edge_types, device):
    model.eval()
    preds, labels = [], []
    
    x_dict = {k: v.to(device) for k, v in data.x_dict.items()}
    edge_index_dict = {k: v.to(device) for k, v in data.edge_index_dict.items()}
    
    for edge_type in target_edge_types:
        edge_label_index = data[edge_type].edge_label_index
        if edge_label_index.numel() == 0: continue
            
        edge_label_index = edge_label_index.to(device)
        edge_label = data[edge_type].edge_label.to(device)
        
        out = model(x_dict, edge_index_dict, edge_type, edge_label_index)
        preds.append(torch.sigmoid(out).cpu().numpy())
        labels.append(edge_label.cpu().numpy())
            
    if not preds: return 0.0
    
    preds = np.concatenate(preds)
    labels = np.concatenate(labels)
    if len(np.unique(labels)) < 2: return 0.0
    
    return roc_auc_score(labels, preds)

def run_optimization(project_name):
    paths = get_project_paths(project_name)
    PYG_DATA_PATH = paths['PYG_DATA_PATH']
    MODEL_PATH = paths['MODEL_PATH']
    METADATA_PATH = paths['METADATA_PATH']
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Training Device: {device} (Full-Batch Training Enabled)")
    
    if not os.path.exists(PYG_DATA_PATH):
        print(f"[Error] PyG Data not found at {PYG_DATA_PATH}. Please run ETL first!")
        return
        
    train_data, val_data, test_data, target_edge_types = prepare_data(PYG_DATA_PATH)
    
    if not target_edge_types:
        print("[Error] No valid edge types found for prediction!")
        return
        
    model = HGTLinkPrediction(
        hidden_channels=128, 
        out_channels=128, 
        data=train_data, 
        dropout=0.3
    ).to(device)
    
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=5)
    
    epochs = 50
    best_val_auc = 0.0
    patience = 10
    no_improve = 0
    
    print("\nStarting Full-Batch Training Loop...")
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    
    from tqdm.auto import tqdm
    pbar = tqdm(range(1, epochs + 1), desc="Training GNN")
    
    for epoch in pbar:
        loss = train_epoch(model, train_data, target_edge_types, optimizer, device)
        val_auc = evaluate(model, val_data, target_edge_types, device)
        scheduler.step(val_auc)
        
        lr = optimizer.param_groups[0]['lr']
        
        if val_auc > best_val_auc:
            best_val_auc = val_auc
            no_improve = 0
            torch.save(model.state_dict(), str(MODEL_PATH))
            pbar.set_postfix({"Loss": f"{loss:.4f}", "Val AUC": f"{val_auc:.4f}", "Best": "Yes"})
        else:
            no_improve += 1
            pbar.set_postfix({"Loss": f"{loss:.4f}", "Val AUC": f"{val_auc:.4f}", "Best": "No"})
            if no_improve >= patience:
                print(f"\nEarly stopping triggered after {patience} epochs without improvement.")
                break
                
    print(f"\nLoading best model (Val AUC: {best_val_auc:.4f}) for Final Evaluation...")
    model.load_state_dict(torch.load(str(MODEL_PATH), map_location=device, weights_only=True))
    test_auc = evaluate(model, test_data, target_edge_types, device)
    print(f"[Success] Final Test AUC: {test_auc:.4f}")

    metadata = load_metadata(METADATA_PATH)
    metadata.update({
        'train_finished_at': utc_now_iso(),
        'model_schema_hash': compute_graph_schema_hash(train_data),
        'best_val_auc': float(best_val_auc),
        'test_auc': float(test_auc),
        'model_path': str(MODEL_PATH),
    })
    save_metadata(METADATA_PATH, metadata)
    print(f"Training metadata saved to {METADATA_PATH}")

if __name__ == '__main__':
    pass

