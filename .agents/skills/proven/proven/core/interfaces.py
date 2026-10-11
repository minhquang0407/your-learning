from abc import ABC, abstractmethod

# --- 1. HỢP ĐỒNG CHO KHO CHỨA ĐỒ THỊ (REPOSITORY) ---
class IGraphRepository(ABC):
    """Giao diện cho việc lưu trữ và truy xuất đồ thị NetworkX gốc."""
    @abstractmethod
    def load_graph(self):
        pass

    @abstractmethod
    def save_graph(self, G):
        pass

# --- 2. HỢP ĐỒNG CHO KHO CHỨA MODEL AI (REPOSITORY) ---
class IModelRepository(ABC):
    """Giao diện cho việc lưu trữ và truy xuất Model AI đã huấn luyện."""
    @abstractmethod
    def load_model(self, model_architecture=None, device=None):
        pass

    @abstractmethod
    def save_model(self, model):
        pass

# --- 3. HỢP ĐỒNG CHO CÔNG CỤ DỰ ĐOÁN (PREDICTOR) ---
class ILinkPredictor(ABC):
    """Giao diện cho logic dự đoán liên kết trong Codebase."""
    @abstractmethod
    def recommend_top_k(self, src_id, top_k=5, src_type=None, dst_type=None, rel_name=None)->list:
        pass

    @abstractmethod
    def scan_relationship(self, id_a, id_b, src_type, dst_type, mode) -> float:
        pass

# --- 4. HỢP ĐỒNG CHO DỮ LIỆU HUẤN LUYỆN (PYG) ---
class ITrainingDataRepository(ABC):
    """Giao diện để lưu/tải dữ liệu PyG (HeteroData)."""
    @abstractmethod
    def save_data(self, data):
        pass

    @abstractmethod
    def load_data(self):
        pass