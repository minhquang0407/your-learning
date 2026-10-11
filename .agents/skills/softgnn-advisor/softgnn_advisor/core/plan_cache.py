import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from softgnn_advisor.config.settings import get_project_paths


@dataclass
class PlanValidationResult:
    valid: bool
    warnings: list


def make_plan_id():
    return datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')


def save_plan_bundle(project, result, repo_path, base='main', head='HEAD', change_source='auto', llm_config=None, plan_id=None, scan_id=None, scan_path=None, scan_fingerprint=None):
    paths = get_project_paths(project)
    plans_dir = Path(paths['PLANS_DIR'])
    latest_path = Path(paths['LATEST_PLAN_PATH'])
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_id = plan_id or make_plan_id()
    bundle = {
        'plan_id': plan_id,
        'project': project,
        'repo_path': os.path.abspath(repo_path),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'base': base,
        'head': head,
        'change_source': change_source,
        'repo_fingerprint': build_repo_fingerprint(repo_path, result.plans),
        'scan_id': scan_id,
        'scan_path': scan_path,
        'scan_fingerprint': scan_fingerprint or {},
        'targets': [_target_to_dict(target) for target in result.targets],
        'plans': [_plan_to_dict(plan) for plan in result.plans],
        'warnings': list(result.warnings or []),
        'llm': _llm_to_dict(llm_config),
    }
    plan_path = plans_dir / f'{plan_id}.json'
    _write_json(plan_path, bundle)
    _write_json(latest_path, bundle)
    return str(plan_path), str(latest_path), bundle


def load_plan_bundle(project, plan=None):
    paths = get_project_paths(project)
    if plan:
        candidate = Path(plan)
        if not candidate.exists():
            candidate = Path(paths['PLANS_DIR']) / (plan if plan.endswith('.json') else f'{plan}.json')
    else:
        candidate = Path(paths['LATEST_PLAN_PATH'])
    if not candidate.exists():
        raise FileNotFoundError(f'Saved plan not found: {candidate}')
    with open(candidate, 'r', encoding='utf-8') as f:
        return json.load(f), str(candidate)


def validate_plan_bundle(bundle, repo_path):
    warnings = []
    saved = bundle.get('repo_fingerprint', {})
    current = build_repo_fingerprint(repo_path, _plans_from_bundle(bundle))
    if saved.get('git_head') and current.get('git_head') and saved.get('git_head') != current.get('git_head'):
        warnings.append(f"Git HEAD changed: saved {saved.get('git_head')} current {current.get('git_head')}")
    saved_hashes = saved.get('source_hashes', {})
    current_hashes = current.get('source_hashes', {})
    for rel_path, saved_hash in saved_hashes.items():
        current_hash = current_hashes.get(rel_path)
        if current_hash != saved_hash:
            warnings.append(f'Source file changed since plan was created: {rel_path}')
    return PlanValidationResult(valid=not warnings, warnings=warnings)


def build_repo_fingerprint(repo_path, plans):
    repo_path = os.path.abspath(repo_path)
    source_files = sorted({getattr(plan, 'source_file', None) or _infer_source_file_from_plan(plan) for plan in plans})
    source_files = [path for path in source_files if path]
    hashes = {}
    for rel_path in source_files:
        abs_path = os.path.join(repo_path, rel_path.replace('/', os.sep))
        if os.path.exists(abs_path):
            hashes[rel_path.replace('\\', '/')] = _sha256(abs_path)
        else:
            hashes[rel_path.replace('\\', '/')] = None
    return {
        'git_head': _git_head(repo_path),
        'source_hashes': hashes,
    }


def _target_to_dict(target):
    return {
        'node_id': target.node_id,
        'source_file': target.source_file,
        'reason': target.reason,
        'priority': target.priority,
        'evidence': list(target.evidence or []),
        'suggested_file': target.suggested_file,
    }


def _plan_to_dict(plan):
    return {
        'target_id': plan.target_id,
        'source_file': getattr(plan, 'source_file', ''),
        'test_file': plan.test_file,
        'test_names': list(plan.test_names or []),
        'rationale': plan.rationale,
        'code': plan.code,
        'source_file': getattr(plan, 'source_file', ''),
        'assumptions': list(plan.assumptions or []),
    }


def _plans_from_bundle(bundle):
    class PlanProxy:
        pass
    plans = []
    targets_by_id = {t.get('node_id'): t for t in bundle.get('targets', [])}
    for item in bundle.get('plans', []):
        proxy = PlanProxy()
        proxy.target_id = item.get('target_id')
        proxy.source_file = item.get('source_file') or targets_by_id.get(proxy.target_id, {}).get('source_file')
        proxy.test_file = item.get('test_file')
        proxy.test_names = item.get('test_names', [])
        proxy.rationale = item.get('rationale', '')
        proxy.code = item.get('code', '')
        proxy.assumptions = item.get('assumptions', [])
        plans.append(proxy)
    return plans


def _infer_source_file_from_plan(plan):
    return getattr(plan, 'source_file', None)


def _llm_to_dict(llm_config):
    if llm_config is None:
        return {}
    return {
        'provider': getattr(llm_config, 'provider', None),
        'model': getattr(llm_config, 'model', None),
        'base_url': getattr(llm_config, 'base_url', None),
    }


def _write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, sort_keys=True)


def _sha256(abs_path):
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


def bundle_to_generation_plans(bundle):
    from softgnn_advisor.core.test_generation_agent import GeneratedTestPlan
    plans = []
    targets_by_id = {target.get('node_id'): target for target in bundle.get('targets', [])}
    for item in bundle.get('plans', []):
        plan = GeneratedTestPlan(
            target_id=item.get('target_id'),
            test_file=item.get('test_file'),
            test_names=item.get('test_names', []),
            rationale=item.get('rationale', ''),
            code=item.get('code', ''),
            assumptions=item.get('assumptions', []),
            source_file=item.get('source_file') or targets_by_id.get(item.get('target_id'), {}).get('source_file', ''),
        )
        plans.append(plan)
    return plans

