import os
import subprocess
from dataclasses import dataclass, field


@dataclass
class ScanFallbackDecision:
    base: str
    head: str
    change_source: str = 'git'
    reason: str = 'original'
    messages: list = field(default_factory=list)
    fallback_used: bool = False
    changed_files: list = field(default_factory=list)


def _run_git(repo_path, args):
    try:
        result = subprocess.run(
            ['git'] + args,
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ''


def git_changed_files(repo_path, base, head):
    diff_ref = f'{base}...{head}'
    output = _run_git(repo_path, ['diff', '--name-only', diff_ref])
    return [line.strip().replace('\\', '/') for line in output.splitlines() if line.strip()]


def git_worktree_dirty(repo_path):
    return bool(_run_git(repo_path, ['status', '--porcelain']))


def recent_pull_base(repo_path):
    output = _run_git(repo_path, ['reflog', '--format=%H%x09%gs', '-n', '8'])
    rows = [line.split('\t', 1) for line in output.splitlines() if '\t' in line]
    if len(rows) < 2:
        return None
    current_subject = rows[0][1].lower()
    previous_hash = rows[1][0]
    recent_keywords = ('pull', 'merge', 'rebase', 'checkout')
    if any(keyword in current_subject for keyword in recent_keywords):
        return previous_hash
    return None


def resolve_read_only_scan_range(repo_path, base='main', head='HEAD'):
    messages = []
    files = git_changed_files(repo_path, base, head)
    if files:
        return ScanFallbackDecision(base, head, 'git', 'original', messages, False, files)

    messages.append(f'Smart scan: no changes found in {base}...{head}.')
    reflog_base = recent_pull_base(repo_path)
    if reflog_base:
        reflog_files = git_changed_files(repo_path, reflog_base, head)
        if reflog_files:
            messages.append(f'Smart scan: using recent checkout range {reflog_base[:7]}...{head}.')
            return ScanFallbackDecision(reflog_base, head, 'git', 'recent-reflog', messages, True, reflog_files)
        messages.append(f'Smart scan: recent checkout range {reflog_base[:7]}...{head} also has no changed files.')
    return ScanFallbackDecision(base, head, 'git', 'empty', messages, False, [])


def generate_same_branch_fallback(repo_path, base='main', head='HEAD'):
    messages = [f'No changed files found for {base}...{head}.']
    if git_worktree_dirty(repo_path):
        messages.append('You have uncommitted changes. Commit first for a reproducible generate run, or explicitly pass --source filesystem.')
        return ScanFallbackDecision(base, head, 'git', 'dirty-worktree', messages, False, [])
    files = git_changed_files(repo_path, 'HEAD~1', 'HEAD')
    if files:
        messages.append('Detected changes in HEAD~1...HEAD.')
        return ScanFallbackDecision('HEAD~1', 'HEAD', 'git', 'same-branch-commit', messages, True, files)
    messages.append('No same-branch commit diff was found in HEAD~1...HEAD.')
    return ScanFallbackDecision(base, head, 'git', 'empty', messages, False, [])
