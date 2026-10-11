from pathlib import PurePosixPath

# Files that are useful for code ownership / bug relevance.
RELEVANT_FILE_EXTENSIONS = {
    '.py', '.ipynb', '.js', '.jsx', '.ts', '.tsx',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg',
    '.txt', '.md', '.rst', '.sql', '.sh', '.ps1',
}

SOURCE_CODE_EXTENSIONS = {'.py', '.ipynb', '.js', '.jsx', '.ts', '.tsx'}

# Generated outputs, binary reports, caches, and dependency folders add noise.
NOISY_PATH_PARTS = {
    '.git', '.venv', 'venv', 'env', '__pycache__', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', 'node_modules', 'dist', 'build',
    'data_output', 'outputs', 'artifacts', 'checkpoints', 'models',
    'temp', 'tmp', '.temp', '.tmp', 'site-packages', 'dist-packages',
    '.tox', '.nox', '.eggs', 'unpacked', 'extracted', 'cache', '.cache',
}

NOISY_FILE_EXTENSIONS = {
    '.pkl', '.pt', '.pth', '.onnx', '.pdf', '.png', '.jpg', '.jpeg',
    '.gif', '.webp', '.svg', '.ico', '.csv', '.xlsx', '.xls', '.parquet',
    '.zip', '.tar', '.gz', '.7z', '.rar', '.mp4', '.avi', '.mov', '.mp3',
}


def is_noisy_dir(dir_name: str, rel_path: str = "") -> bool:
    """Return True if a directory name or repo-relative path belongs to noisy/external/temporary folders."""
    name_clean = str(dir_name or '').strip().lower()
    if not name_clean:
        return False
    if name_clean in NOISY_PATH_PARTS or name_clean.endswith('.egg-info'):
        return True
    if rel_path:
        norm = normalize_repo_path(rel_path).lower()
        parts = set(norm.split('/'))
        if parts & NOISY_PATH_PARTS:
            return True
        for noisy in ('site-packages', 'dist-packages', '__pycache__', '.venv', 'node_modules'):
            if noisy in norm:
                return True
    return False


def normalize_repo_path(path: str) -> str:
    """Normalize repo-relative paths to stable POSIX style."""
    return str(path).replace('\\', '/').strip('/')


def is_relevant_file(path: str, allow_docs: bool = True) -> bool:
    """Return True when a file should participate in relevance/ownership scoring."""
    norm = normalize_repo_path(path)
    if not norm:
        return False

    parts = set(part for part in norm.split('/') if part)
    if parts & NOISY_PATH_PARTS:
        return False

    suffix = PurePosixPath(norm).suffix.lower()
    if suffix in NOISY_FILE_EXTENSIONS:
        return False

    if not allow_docs and suffix in {'.md', '.rst', '.txt'}:
        return False

    return suffix in RELEVANT_FILE_EXTENSIONS


def is_source_code_file(path: str) -> bool:
    """Return True for source-code files preferred by bug semantic matching."""
    norm = normalize_repo_path(path)
    if not norm:
        return False
    parts = set(part for part in norm.split('/') if part)
    if parts & NOISY_PATH_PARTS:
        return False
    suffix = PurePosixPath(norm).suffix.lower()
    if PurePosixPath(norm).name == '__init__.py':
        return False
    if suffix in NOISY_FILE_EXTENSIONS:
        return False
    return suffix in SOURCE_CODE_EXTENSIONS


NOISY_DEVELOPER_NAMES = {
    '', 'unknown', 'none', 'null', 'anonymous', 'admin', 'root', 'mac',
    'localhost', 'user', 'users', 'nguye', 'pc', 'desktop', 'laptop',
}


def is_valid_developer_name(name: str) -> bool:
    """Return False for machine/local placeholder identities."""
    normalized = str(name or '').strip().lower()
    if normalized in NOISY_DEVELOPER_NAMES:
        return False
    if len(normalized) < 3:
        return False
    # Very generic one-word machine names are usually not useful as team identities.
    if normalized.startswith('desktop-') or normalized.startswith('laptop-'):
        return False
    return True
