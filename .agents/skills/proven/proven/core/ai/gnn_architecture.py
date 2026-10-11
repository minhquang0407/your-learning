import torch
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, HGTConv, Linear, to_hetero

# --- DECODER ---
class InteractionMLP(torch.nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim, dropout):
        super().__init__()
        self.lin1 = torch.nn.Linear(input_dim * 3, hidden_dim)
        self.lin2 = torch.nn.Linear(hidden_dim, hidden_dim // 2)
        self.lin3 = torch.nn.Linear(hidden_dim // 2, output_dim)
        self.dropout = torch.nn.Dropout(p=dropout)

    def forward(self, z_src, z_dst):
        combined = torch.cat([z_src, z_dst, z_src * z_dst], dim=1)
        h = self.lin1(combined)
        h = F.relu(h)
        h = self.dropout(h)
        h = self.lin2(h)
        h = F.relu(h)
        h = self.dropout(h)
        h = self.lin3(h)
        return h.view(-1)

class HGTEncoder(torch.nn.Module):
    def __init__(self, hidden_channels, lin_dict, convs, dropout):
        super().__init__()
        self.lin_dict = lin_dict
        self.convs = convs
        self.dropout = dropout

    def forward(self, x_dict, edge_index_dict):
        # Determine dtype dynamically based on projection layers
        first_lin = list(self.lin_dict.values())[0]
        dtype = first_lin.weight.dtype if hasattr(first_lin, 'weight') and first_lin.weight is not None else torch.float32
        
        x_dict = {k: v.to(dtype) for k, v in x_dict.items()}
        x_start = {}
        for node_type, x in x_dict.items():
            x_start[node_type] = self.lin_dict[node_type](x).relu_()
            x_start[node_type] = self.dropout(x_start[node_type])

        for conv in self.convs:
            x_start = conv(x_start, edge_index_dict)
            
        return x_start

class HGTLinkPrediction(torch.nn.Module):
    def __init__(self, hidden_channels, out_channels, data=None, metadata=None, dropout=0.5, num_heads=4, num_layers=3):
        super().__init__()
        if metadata is None:
            if data is not None:
                self.metadata = data.metadata()
            else:
                raise ValueError("Must provide either 'data' or 'metadata' to initialize model!")
        else:
            self.metadata = metadata
            
        node_types, edge_types = self.metadata
        
        # 1. INPUT PROJECTION
        self.lin_dict = torch.nn.ModuleDict()
        for node_type in node_types:
            in_dim = data[node_type].x.size(1) if data is not None else 768
            self.lin_dict[node_type] = Linear(in_dim, hidden_channels)

        # 2. HGT LAYERS
        self.convs = torch.nn.ModuleList()
        for _ in range(num_layers):
            conv = HGTConv(hidden_channels, hidden_channels, self.metadata, heads=num_heads)
            self.convs.append(conv)

        self.dropout = torch.nn.Dropout(p=dropout)
        
        # 3. ENCODER WRAPPER
        self.encoder = HGTEncoder(hidden_channels, self.lin_dict, self.convs, self.dropout)

        # 4. DECODER
        self.decoders = torch.nn.ModuleDict()
        for et in edge_types:
            _, rel, _ = et
            if rel.startswith('rev_'): continue
            key = f"__{rel}__"
            self.decoders[key] = InteractionMLP(hidden_channels, 64, 1, dropout)

    def forward(self, x_dict, edge_index_dict, target_edge_type, edge_label_index):
        x_start = self.encoder(x_dict, edge_index_dict)
        
        src_type, rel, dst_type = target_edge_type
        z_src = x_start[src_type][edge_label_index[0]]
        z_dst = x_start[dst_type][edge_label_index[1]]

        key = f"__{rel}__"
        if key in self.decoders:
            return self.decoders[key](z_src, z_dst)
        else:
            return torch.zeros(z_src.size(0), device=z_src.device)