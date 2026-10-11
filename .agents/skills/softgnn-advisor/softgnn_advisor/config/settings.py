import os
from pathlib import Path


def get_data_root() -> Path:
    """Resolve the data root directory.

    Priority:
    1. SOFTGNN_DATA_DIR environment variable
    2. ~/.softgnn (cross-platform user home)

    For backward compatibility, if a legacy data_output/ directory exists
    next to the installed package, a migration hint is printed once.
    """
    env = os.environ.get('SOFTGNN_DATA_DIR')
    if env:
        root = Path(env)
        root.mkdir(parents=True, exist_ok=True)
        return root
    root = Path.home() / '.softgnn'
    root.mkdir(parents=True, exist_ok=True)
    return root


DATA_DIR = get_data_root()


def get_project_paths(project_name: str) -> dict:
    project_dir = DATA_DIR / project_name
    
    graph_dir = project_dir / "graph"
    training_dir = project_dir / "training"
    models_dir = project_dir / "models"
    scans_dir = project_dir / "scans"
    reports_dir = project_dir / "reports"
    
    for d in [project_dir, graph_dir, training_dir, models_dir, scans_dir, reports_dir]:
        d.mkdir(parents=True, exist_ok=True)
        
    return {
        "GRAPH_PATH": graph_dir / "relationship_graph.pkl",
        "NODES_DATA_PATH": project_dir / "nodes_data.csv",
        "PYG_DATA_PATH": training_dir / "pyg_data.pt",
        "MODEL_PATH": models_dir / "model.pt",
        "METADATA_PATH": project_dir / "metadata.json",
        "DEVELOPER_ALIASES_PATH": project_dir / "developer_aliases.json",
        "CONTRACTS_PATH": project_dir / "contracts.json",
        "TEST_COVERAGE_EDGES_PATH": project_dir / "test_coverage_edges.json",
        "RUNTIME_TEST_COVERAGE_EDGES_PATH": project_dir / "runtime_test_coverage_edges.json",
        "FILESYSTEM_SNAPSHOT_PATH": project_dir / "filesystem_snapshot.json",
        "SCANS_DIR": project_dir / "scans",
        "LATEST_SCAN_PATH": project_dir / "scans" / "latest_scan.json",
        "PLANS_DIR": project_dir / "plans",
        "LATEST_PLAN_PATH": project_dir / "plans" / "latest_plan.json",
        "COVERAGE_WORK_DIR": project_dir / "coverage",
        "REPORTS_DIR": reports_dir,
        "LATEST_REPORT_PATH": reports_dir / "latest_report.html",
    }

INPUT_DIM = 385
HIDDEN_DIM = 256
OUTPUT_DIM = 128
LEARNING_RATE = 0.01
EPOCHS = 100
BATCH_SIZE = 2048
MIN_EDGE_COUNT = 500
