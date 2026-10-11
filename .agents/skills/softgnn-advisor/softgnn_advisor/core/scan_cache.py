import hashlib
import json
import os
import subprocess
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

from softgnn_advisor.config.settings import get_project_paths
from softgnn_advisor.core.change_provider import ChangedFile, ChangedHunk
from softgnn_advisor.core.pr_scanner import (
    ChangedNode,
    ContractChange,
    ImpactHotspot,
    MissingCoverage,
    PRScanResult,
    RelatedTest,
    ReviewerRecommendation,
    TestSuggestion,
)


def make_scan_id():
    return datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')


def save_scan_bundle(project, result, repo_path, base='main', head='HEAD', change_source='auto', mode='hybrid', scan_id=None):
    paths = get_project_paths(project)
    scans_dir = Path(paths['SCANS_DIR'])
    latest_path = Path(paths['LATEST_SCAN_PATH'])
    scans_dir.mkdir(parents=True, exist_ok=True)
    scan_id = scan_id or make_scan_id()
    bundle = {
        'scan_id': scan_id,
        'project': project,
        'repo_path': os.path.abspath(repo_path),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'base': base,
        'head': head,
        'change_source': change_source,
        'mode': mode,
        'repo_fingerprint': build_scan_fingerprint(repo_path, result),
        'result': scan_result_to_dict(result),
    }
    scan_path = scans_dir / f'{scan_id}.json'
    _write_json(scan_path, bundle)
    _write_json(latest_path, bundle)
    return str(scan_path), str(latest_path), bundle


def load_scan_bundle(project, scan=None):
    paths = get_project_paths(project)
    if scan and scan != 'latest':
        candidate = Path(scan)
        if not candidate.exists():
            candidate = Path(paths['SCANS_DIR']) / (scan if str(scan).endswith('.json') else f'{scan}.json')
    else:
        candidate = Path(paths['LATEST_SCAN_PATH'])
    if not candidate.exists():
        raise FileNotFoundError(f'Saved scan not found: {candidate}')
    with open(candidate, 'r', encoding='utf-8') as f:
        return json.load(f), str(candidate)


def validate_scan_bundle(bundle, repo_path):
    warnings = []
    saved = bundle.get('repo_fingerprint', {})
    current_head = _git_head(repo_path)
    if saved.get('git_head') and current_head and saved.get('git_head') != current_head:
        warnings.append(f"Git HEAD changed since scan: saved {saved.get('git_head')} current {current_head}")
    for rel_path, saved_hash in (saved.get('changed_file_hashes') or {}).items():
        current_hash = _file_hash_or_none(repo_path, rel_path)
        if current_hash != saved_hash:
            warnings.append(f'Changed file changed since scan was created: {rel_path}')
    return {'valid': not warnings, 'warnings': warnings}


def scan_bundle_to_result(bundle):
    return scan_result_from_dict(bundle.get('result', {}))


def scan_result_to_dict(result):
    return {
        'changed_files': [_dataclass_to_dict(item) for item in result.changed_files],
        'changed_nodes': [_dataclass_to_dict(item) for item in result.changed_nodes],
        'impact_hotspots': [_dataclass_to_dict(item) for item in result.impact_hotspots],
        'reviewers': [_dataclass_to_dict(item) for item in result.reviewers],
        'suggested_tests': [_dataclass_to_dict(item) for item in result.suggested_tests],
        'warnings': list(result.warnings or []),
        'contract_changes': [_dataclass_to_dict(item) for item in result.contract_changes],
        'related_tests': [_dataclass_to_dict(item) for item in result.related_tests],
        'missing_coverage': [_dataclass_to_dict(item) for item in result.missing_coverage],
        'change_source': result.change_source,
    }


def scan_result_from_dict(data):
    return PRScanResult(
        changed_files=[_changed_file_from_dict(item) for item in data.get('changed_files', [])],
        changed_nodes=[_from_dict(ChangedNode, item) for item in data.get('changed_nodes', [])],
        impact_hotspots=[_from_dict(ImpactHotspot, item) for item in data.get('impact_hotspots', [])],
        reviewers=[_from_dict(ReviewerRecommendation, item) for item in data.get('reviewers', [])],
        suggested_tests=[_from_dict(TestSuggestion, item) for item in data.get('suggested_tests', [])],
        warnings=list(data.get('warnings', [])),
        contract_changes=[_from_dict(ContractChange, item) for item in data.get('contract_changes', [])],
        related_tests=[_from_dict(RelatedTest, item) for item in data.get('related_tests', [])],
        missing_coverage=[_from_dict(MissingCoverage, item) for item in data.get('missing_coverage', [])],
        change_source=data.get('change_source', 'git'),
    )


def build_scan_fingerprint(repo_path, result):
    changed_paths = sorted({item.path for item in result.changed_files})
    return {
        'git_head': _git_head(repo_path),
        'changed_file_hashes': {path: _file_hash_or_none(repo_path, path) for path in changed_paths},
    }


def _dataclass_to_dict(item):
    if is_dataclass(item):
        data = asdict(item)
    else:
        data = dict(item)
    if 'key' in data and isinstance(data['key'], tuple):
        data['key'] = list(data['key'])
    return data


def _from_dict(cls, data):
    item = dict(data)
    if 'key' in item and isinstance(item['key'], list):
        item['key'] = tuple(item['key'])
    return cls(**item)


def _changed_file_from_dict(data):
    item = dict(data)
    item['hunks'] = [_from_dict(ChangedHunk, hunk) for hunk in item.get('hunks', [])]
    return ChangedFile(**item)


def _write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, sort_keys=True)


def _file_hash_or_none(repo_path, rel_path):
    abs_path = os.path.join(os.path.abspath(repo_path), rel_path.replace('/', os.sep))
    if not os.path.exists(abs_path):
        return None
    digest = hashlib.sha256()
    with open(abs_path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(repo_path):
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None
