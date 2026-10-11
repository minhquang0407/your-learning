import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from softgnn_advisor.config.settings import get_project_paths


@dataclass
class ChangedHunk:
    start_line: int
    end_line: int


@dataclass
class ChangedFile:
    path: str
    hunks: list = field(default_factory=list)
    added_lines: int = 0
    deleted_lines: int = 0
    status: str = 'modified'
    source: str = 'git'


@dataclass
class ChangeSet:
    source: str
    base: str | None
    head: str | None
    files: list
    warnings: list = field(default_factory=list)


def normalize_repo_path(path):
    return path.replace('\\', '/').strip('/')


def is_python_file(path):
    return normalize_repo_path(path).endswith('.py')


def is_git_repo(repo_path):
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=True,
        )
        return result.stdout.strip().lower() == 'true'
    except Exception:
        return False


def snapshot_path_for_project(project):
    return str(get_project_paths(project)['FILESYSTEM_SNAPSHOT_PATH'])


def load_filesystem_snapshot(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_filesystem_snapshot(path, snapshot):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)


def build_filesystem_snapshot(repo_path, include_tests=True):
    repo_path = os.path.abspath(repo_path)
    files = {}
    for root, dirs, filenames in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in {'.git', '.venv', 'venv', 'env', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}]
        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            abs_path = os.path.join(root, filename)
            rel_path = normalize_repo_path(os.path.relpath(abs_path, repo_path))
            if not include_tests and (rel_path.startswith('tests/') or '/tests/' in rel_path):
                continue
            try:
                stat = os.stat(abs_path)
                files[rel_path] = {
                    'sha256': _sha256(abs_path),
                    'mtime': stat.st_mtime,
                    'size': stat.st_size,
                }
            except OSError:
                continue
    return {
        'repo_path': repo_path,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'files': files,
    }


def _sha256(abs_path):
    digest = hashlib.sha256()
    with open(abs_path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def whole_file_hunk(repo_path, rel_path):
    abs_path = os.path.join(repo_path, rel_path.replace('/', os.sep))
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            line_count = sum(1 for _ in f)
    except OSError:
        line_count = 1
    return ChangedHunk(1, max(1, line_count))


class GitChangeProvider:
    source = 'git'

    def __init__(self, repo_path):
        self.repo_path = os.path.abspath(repo_path)

    def detect_changes(self, base='main', head='HEAD'):
        warnings = []
        diff_ref = f'{base}...{head}'
        name_status = self._run_git(['diff', '--name-status', diff_ref], warnings)
        files = []
        for line in name_status.splitlines():
            parts = line.strip().split('\t')
            if not parts:
                continue
            status_code = parts[0]
            if status_code.startswith('R') and len(parts) >= 3:
                rel_path = normalize_repo_path(parts[2])
                status = 'renamed'
            elif len(parts) >= 2:
                rel_path = normalize_repo_path(parts[1])
                status = self._status_name(status_code)
            else:
                continue
            diff_output = self._run_git(['diff', '--unified=0', diff_ref, '--', rel_path], warnings)
            changed = self._parse_file_diff(rel_path, diff_output, status=status)
            files.append(changed)
        return ChangeSet(self.source, base, head, files, warnings)

    def _run_git(self, args, warnings):
        try:
            result = subprocess.run(
                ['git'] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            warnings.append(f"git {' '.join(args)} failed: {e.stderr.strip() or e.stdout.strip()}")
            return ''

    def _status_name(self, status_code):
        code = status_code[:1]
        return {
            'A': 'added',
            'M': 'modified',
            'D': 'deleted',
            'R': 'renamed',
            'C': 'copied',
        }.get(code, 'unknown')

    def _parse_file_diff(self, rel_path, diff_output, status='modified'):
        hunks = []
        added = 0
        deleted = 0
        import re
        for line in diff_output.splitlines():
            header = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if header:
                start = int(header.group(3))
                length = int(header.group(4) or '1')
                end = start if length == 0 else start + length - 1
                hunks.append(ChangedHunk(start, end))
                continue
            if line.startswith('+++') or line.startswith('---'):
                continue
            if line.startswith('+'):
                added += 1
            elif line.startswith('-'):
                deleted += 1
        if status == 'added' and not hunks and is_python_file(rel_path):
            hunks = [whole_file_hunk(self.repo_path, rel_path)]
        return ChangedFile(rel_path, hunks, added, deleted, status=status, source=self.source)


class FilesystemSnapshotChangeProvider:
    source = 'filesystem'

    def __init__(self, repo_path, snapshot_path):
        self.repo_path = os.path.abspath(repo_path)
        self.snapshot_path = snapshot_path

    def detect_changes(self, base=None, head=None):
        warnings = []
        previous = load_filesystem_snapshot(self.snapshot_path)
        if previous is None:
            warnings.append('No previous filesystem snapshot found; using full-scan change detection.')
            return FullScanChangeProvider(self.repo_path).detect_changes(base=base, head=head)
        current = build_filesystem_snapshot(self.repo_path)
        old_files = previous.get('files', {})
        new_files = current.get('files', {})
        changed = []
        for rel_path in sorted(set(new_files) - set(old_files)):
            changed.append(ChangedFile(rel_path, [whole_file_hunk(self.repo_path, rel_path)], added_lines=_line_count(self.repo_path, rel_path), status='added', source=self.source))
        for rel_path in sorted(set(old_files) & set(new_files)):
            if old_files[rel_path].get('sha256') != new_files[rel_path].get('sha256'):
                changed.append(ChangedFile(rel_path, [whole_file_hunk(self.repo_path, rel_path)], added_lines=_line_count(self.repo_path, rel_path), status='modified', source=self.source))
        for rel_path in sorted(set(old_files) - set(new_files)):
            changed.append(ChangedFile(rel_path, [], deleted_lines=old_files[rel_path].get('size', 0), status='deleted', source=self.source))
        return ChangeSet(self.source, base, head, changed, warnings)


class FullScanChangeProvider:
    source = 'full-scan'

    def __init__(self, repo_path):
        self.repo_path = os.path.abspath(repo_path)

    def detect_changes(self, base=None, head=None):
        snapshot = build_filesystem_snapshot(self.repo_path)
        files = [
            ChangedFile(rel_path, [whole_file_hunk(self.repo_path, rel_path)], added_lines=_line_count(self.repo_path, rel_path), status='added', source=self.source)
            for rel_path in sorted(snapshot.get('files', {}))
        ]
        warnings = ['Using full-scan change detection; all Python files are treated as added/changed.']
        return ChangeSet(self.source, base, head, files, warnings)


class AutoChangeProvider:
    source = 'auto'

    def __init__(self, project, repo_path):
        self.project = project
        self.repo_path = os.path.abspath(repo_path)
        self.snapshot_path = snapshot_path_for_project(project)

    def detect_changes(self, base='main', head='HEAD'):
        if is_git_repo(self.repo_path):
            changes = GitChangeProvider(self.repo_path).detect_changes(base=base, head=head)
            if changes.files or not changes.warnings:
                changes.source = 'git'
                return changes
            changes.warnings.append('Git change detection produced no files; falling back to filesystem snapshot diff.')
        if os.path.exists(self.snapshot_path):
            changes = FilesystemSnapshotChangeProvider(self.repo_path, self.snapshot_path).detect_changes(base=None, head=None)
            changes.warnings.insert(0, 'Git repository not detected or unusable; using filesystem snapshot diff.')
            return changes
        changes = FullScanChangeProvider(self.repo_path).detect_changes(base=None, head=None)
        changes.warnings.insert(0, 'Git repository not detected or no snapshot exists; using full-scan first-run mode.')
        return changes


def build_change_set(project, repo_path, base='main', head='HEAD', change_source='auto'):
    change_source = change_source or 'auto'
    if change_source == 'git':
        return GitChangeProvider(repo_path).detect_changes(base=base, head=head)
    if change_source == 'filesystem':
        return FilesystemSnapshotChangeProvider(repo_path, snapshot_path_for_project(project)).detect_changes(base=None, head=None)
    if change_source == 'full-scan':
        return FullScanChangeProvider(repo_path).detect_changes(base=None, head=None)
    if change_source == 'auto':
        return AutoChangeProvider(project, repo_path).detect_changes(base=base, head=head)
    raise ValueError("change_source must be one of: auto, git, filesystem, full-scan")


def _line_count(repo_path, rel_path):
    abs_path = os.path.join(repo_path, rel_path.replace('/', os.sep))
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)
    except OSError:
        return 0

