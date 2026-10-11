import pickle
import os
import sys
import networkx as nx
from pathlib import Path
FILE_PATH = Path(__file__).resolve()
PROJECT_DIR = FILE_PATH.parent.parent.parent
sys.path.append(str(PROJECT_DIR))
from proven.core.interfaces import IGraphRepository


class PickleGraphRepository(IGraphRepository):
    """Pickle graph repository for storing and loading NetworkX graphs."""

    def __init__(self, file_path: Path):
        self.file_path = file_path

    def save_graph(self, G):
        """Save NetworkX graph to disk."""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

        try:
            print(f"REPO: Saving graph to {self.file_path}...")
            with open(self.file_path, "wb") as f:
                pickle.dump(G, f, pickle.HIGHEST_PROTOCOL)
            print("REPO: Successfully saved graph.")
            return True

        except Exception as e:
            print(f"REPO ERROR: Failed to save graph: {e}")
            return False

    def load_graph(self) -> nx.Graph:
        """Load graph from disk."""
        if not os.path.exists(self.file_path):
            print(f"REPO WARNING: File does not exist: {self.file_path}")
            return None

        try:
            print(f"REPO: Loading graph from {self.file_path}...")
            with open(self.file_path, "rb") as f:
                G = pickle.load(f)

            print(f"REPO: Successfully loaded graph. (Nodes: {G.vcount()}, Edges: {G.ecount()})")
            return G

        except Exception as e:
            print(f"REPO ERROR: Failed to read graph file: {e}")
            return None
