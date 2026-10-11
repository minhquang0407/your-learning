import os
import gzip
import pickle

from proven.core.interfaces import ITrainingDataRepository
import torch
from torch_geometric.data.storage import BaseStorage, GlobalStorage
from torch_geometric.data import Data
from torch_geometric.data.storage import EdgeStorage, NodeStorage
torch.serialization.add_safe_globals([
    BaseStorage,
    GlobalStorage,
    Data,
    EdgeStorage,
    NodeStorage,
    dict
])
class PyGDataRepository(ITrainingDataRepository):
    def __init__(self, data_path, adjacency_path = None):
        self.data_path = str(data_path)
        self.adjacency_path = str(adjacency_path)
    def save_data(self, data):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)

            print(f"REPO: Saving processed data to {self.data_path}...")
            torch.save(data, self.data_path)

        except Exception as e:
            print(f"REPO ERROR: {e}")
            return False

    def load_data(self):
        if not os.path.exists(self.data_path):
            return None
        try:
            print("REPO: Loading processed data...")
            data = torch.load(self.data_path, map_location='cpu')
            return data
        except Exception as e:
            print(f"REPO ERROR: {e}")
            return None

    def load_adjacency(self):
        if not os.path.exists(self.adjacency_path):
            return None
        try:
            print("REPO: Loading adjacency data...")
            with open(self.adjacency_path, 'rb') as f:
                adj = pickle.load(f)
            return adj
        except Exception as e:
            print(f"REPO ERROR: {e}")
            return None

    def save_adjacency(self, data):
        try:
            os.makedirs(os.path.dirname(self.adjacency_path), exist_ok=True)
            with open(self.adjacency_path, 'wb') as f:
                pickle.dump(data, f)
            return True
        except Exception as e:
            print(f"REPO ERROR: {e}")
            return False
