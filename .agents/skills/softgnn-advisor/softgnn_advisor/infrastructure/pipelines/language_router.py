import json
import os
from pathlib import Path


def detect_project_language(repo_path: str) -> str:
    """Detect the primary programming language of a repository.

    Returns: 'python', 'typescript', 'javascript', 'go', 'rust', 'java', 'cpp', or 'unknown'.
    """
    repo_path = os.path.abspath(repo_path)

    # 1. Check characteristic manifest files
    py_manifests = ['pyproject.toml', 'setup.py', 'setup.cfg', 'requirements.txt', 'Pipfile']
    has_py_manifest = any(os.path.exists(os.path.join(repo_path, m)) for m in py_manifests)

    ts_js_manifests = ['package.json', 'tsconfig.json']
    has_ts_js_manifest = any(os.path.exists(os.path.join(repo_path, m)) for m in ts_js_manifests)

    has_go_manifest = os.path.exists(os.path.join(repo_path, 'go.mod'))
    has_rust_manifest = os.path.exists(os.path.join(repo_path, 'Cargo.toml'))
    has_java_manifest = any(os.path.exists(os.path.join(repo_path, m)) for m in ['pom.xml', 'build.gradle', 'build.gradle.kts'])

    # Specific check for package.json to distinguish TypeScript vs JavaScript
    if has_ts_js_manifest and not has_py_manifest:
        if os.path.exists(os.path.join(repo_path, 'tsconfig.json')):
            return 'typescript'
        pkg_path = os.path.join(repo_path, 'package.json')
        if os.path.exists(pkg_path):
            try:
                pkg_data = json.loads(Path(pkg_path).read_text(encoding='utf-8', errors='ignore'))
                deps = {**pkg_data.get('dependencies', {}), **pkg_data.get('devDependencies', {})}
                if 'typescript' in deps or any(k.startswith('@types/') for k in deps):
                    return 'typescript'
            except Exception:
                pass
        return 'javascript'

    if has_py_manifest and not has_ts_js_manifest and not has_go_manifest:
        return 'python'
    if has_go_manifest:
        return 'go'
    if has_rust_manifest:
        return 'rust'
    if has_java_manifest:
        return 'java'

    # 2. Count extensions if manifests are mixed, absent, or ambiguous
    ext_counts = {
        'python': 0,
        'typescript': 0,
        'javascript': 0,
        'go': 0,
        'rust': 0,
        'java': 0,
        'cpp': 0,
    }
    ext_map = {
        '.py': 'python',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.mjs': 'javascript',
        '.go': 'go',
        '.rs': 'rust',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'cpp',
        '.cc': 'cpp',
        '.h': 'cpp',
        '.hpp': 'cpp',
    }

    ignore_dirs = {'.git', '.venv', 'venv', 'node_modules', 'dist', 'build', '__pycache__', 'target', 'vendor'}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        for file in files:
            _, ext = os.path.splitext(file.lower())
            lang = ext_map.get(ext)
            if lang:
                ext_counts[lang] += 1

    total_files = sum(ext_counts.values())
    if total_files > 0:
        dominant_lang = max(ext_counts, key=ext_counts.get)
        if ext_counts[dominant_lang] > 0:
            return dominant_lang

    # Fallback to python
    return 'python'
