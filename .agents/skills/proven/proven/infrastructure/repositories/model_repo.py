import torch
import os
import pickle
import sys
from pathlib import Path
FILE_PATH = Path(__file__).resolve()
PROJECT_DIR = FILE_PATH.parent.parent.parent
sys.path.append(str(PROJECT_DIR))
from proven.core.interfaces import IModelRepository


class ModelRepository(IModelRepository):
    """AI Model repository. Supports PyTorch (.pth) and Pickle (.pkl)."""

    def __init__(self, file_path: Path):
        self.file_path = str(file_path)

    def save_model(self, model):
        """Save model to disk."""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

        try:
            print(f"REPO: Saving model to {self.file_path}...")

            if isinstance(model, torch.nn.Module):
                torch.save(model.state_dict(), self.file_path)
            else:
                with open(self.file_path, "wb") as f:
                    pickle.dump(model, f)

            print("REPO: Successfully saved model.")
            return True
        except Exception as e:
            print(f"REPO ERROR: Failed to save model: {e}")
            return False

    def load_model(self, model=None, device=None):
        """Load model from disk."""
        if not os.path.exists(self.file_path):
            print(f"REPO WARNING: Model file not found: {self.file_path}")
            return None

        try:
            if model is not None:
                if device is None:
                    device = torch.device('cpu')

                state_dict = torch.load(self.file_path, map_location=device)
                model.load_state_dict(state_dict)
                print("REPO: Loaded PyTorch weights.")
                return model

            with open(self.file_path, "rb") as f:
                model = pickle.load(f)
                print("REPO: Loaded Pickle model.")
                return model

        except Exception as e:
            print(f"REPO ERROR: Error loading model: {e}")
            return None
