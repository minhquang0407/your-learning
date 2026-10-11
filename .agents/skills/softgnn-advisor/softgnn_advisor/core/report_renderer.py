import html
import json
import shutil
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

from softgnn_advisor.config.settings import get_project_paths


def _safe(value):
    return html.escape(str(value if value is not None else ''), quote=True)


def _to_dict(obj):
    if obj is None:
        return None
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return obj
    data = {}
    for key in dir(obj):
        if key.startswith('_'):
            continue
        try:
            value = getattr(obj, key)
        except Exception:
            continue
        if callable(value):
            continue
        if isinstance(value, (str, int, float, bool, list, dict, type(None))):
            data[key] = value
    return data


def _edge_to_dict(edge):
    return _to_dict(edge) or {}


def _verification_to_dict(item):
    data = _to_dict(item) or {}
    data['proof_edges'] = [_edge_to_dict(e) for e in getattr(item, 'proof_edges', [])]
    return data


def build_generate_report_payload(project, scan_result=None, plan_result=None, apply_result=None, repo_path=None, pr_scan_result=None):
    scan = scan_result or pr_scan_result
    plans = list(getattr(plan_result, 'plans', None) or getattr(apply_result, 'plans', None) or [])
    verification = list(getattr(apply_result, 'verification_results', None) or [])
    runtime_result = getattr(apply_result, 'runtime_result', None)
    runtime_edges = list(getattr(runtime_result, 'runtime_edges', None) or [])
    files_written = list(getattr(apply_result, 'files_written', None) or [])
    failures = list(getattr(apply_result, 'failures', None) or [])

    proof_pass = sum(1 for item in verification if getattr(item, 'proof_status', 'skipped') == 'pass')
    proof_fail = sum(1 for item in verification if getattr(item, 'proof_status', 'skipped') == 'fail')
    proof_skipped = sum(1 for item in verification if getattr(item, 'proof_status', 'skipped') == 'skipped')
    rolled_back = sum(1 for item in verification if 'rolled_back' in str(getattr(item, 'status', '')))

    payload = {
        'project': project,
        'repo_path': repo_path,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'summary': {
            'changed_files': len(getattr(scan, 'changed_files', []) or []),
            'changed_nodes': len(getattr(scan, 'changed_nodes', []) or []),
            'missing_coverage': len(getattr(scan, 'missing_coverage', []) or []),
            'plans': len(plans),
            'blocks_kept': len(files_written),
            'blocks_rolled_back': rolled_back,
            'proof_pass': proof_pass,
            'proof_fail': proof_fail,
            'proof_skipped': proof_skipped,
            'runtime_edges': len(runtime_edges),
        },
        'scan': {
            'change_source': getattr(scan, 'change_source', None),
            'changed_files': [_to_dict(x) for x in (getattr(scan, 'changed_files', []) or [])],
            'changed_nodes': [_to_dict(x) for x in (getattr(scan, 'changed_nodes', []) or [])],
            'missing_coverage': [_to_dict(x) for x in (getattr(scan, 'missing_coverage', []) or [])],
            'impact_hotspots': [_to_dict(x) for x in (getattr(scan, 'impact_hotspots', []) or [])],
            'reviewers': [_to_dict(x) for x in (getattr(scan, 'reviewers', []) or [])],
            'suggested_tests': [_to_dict(x) for x in (getattr(scan, 'suggested_tests', []) or [])],
            'related_tests': [_to_dict(x) for x in (getattr(scan, 'related_tests', []) or [])],
            'contract_changes': [_to_dict(x) for x in (getattr(scan, 'contract_changes', []) or [])],
        },
        'plans': [_to_dict(p) for p in plans],
        'verification': [_verification_to_dict(v) for v in verification],
        'runtime_edges': [_edge_to_dict(e) for e in runtime_edges],
        'warnings': list(getattr(scan, 'warnings', []) or []) + list(getattr(apply_result, 'warnings', []) or []),
        'failures': [_to_dict(f) for f in failures],
    }
    return payload


def _metric_cards(summary):
    labels = [
        ('Changed files', 'changed_files'), ('Changed nodes', 'changed_nodes'),
        ('Missing coverage', 'missing_coverage'), ('Generated plans', 'plans'),
        ('Blocks kept', 'blocks_kept'), ('Rolled back', 'blocks_rolled_back'),
        ('Proof PASS', 'proof_pass'), ('Proof FAIL', 'proof_fail'),
        ('Runtime edges', 'runtime_edges'),
    ]
    return ''.join(
        f'<div class="metric"><span>{_safe(label)}</span><strong>{_safe(summary.get(key, 0))}</strong></div>'
        for label, key in labels
    )


def _changed_nodes(scan):
    rows = []
    for node in scan.get('changed_nodes', [])[:30]:
        rows.append(f"<tr><td>{_safe(node.get('node_type') or node.get('type'))}</td><td><code>{_safe(node.get('full_id') or node.get('label'))}</code></td><td>{_safe(node.get('source_file'))}</td></tr>")
    return '<p class="muted">No changed graph nodes.</p>' if not rows else '<table><thead><tr><th>Type</th><th>ID</th><th>File</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'


def _proof_cards(payload):
    cards = []
    plans_by_target = {p.get('target_id'): p for p in payload.get('plans', [])}
    for item in payload.get('verification', []):
        status = item.get('proof_status', 'skipped')
        badge = {'pass': 'ok', 'fail': 'bad', 'skipped': 'skip'}.get(status, 'skip')
        icon = {'pass': '✅', 'fail': '❌', 'skipped': '—'}.get(status, '—')
        plan = plans_by_target.get(item.get('target_id'), {})
        cards.append(f"""
        <article class="proof-card {badge}">
          <div class="proof-head"><span class="badge {badge}">{icon} PROOF {_safe(status).upper()}</span><span>{_safe(item.get('status'))}</span></div>
          <h3>{_safe(item.get('target_id'))}</h3>
          <p><b>Test:</b> <code>{_safe(item.get('pytest_target') or item.get('test_file'))}</code></p>
          <p><b>Source:</b> {_safe(plan.get('source_file'))}</p>
          <p class="muted">{_safe(item.get('proof_message'))}</p>
        </article>
        """)
    return '<p class="muted">No apply/proof results yet.</p>' if not cards else ''.join(cards)


def _impact_section(scan):
    hotspots = scan.get('impact_hotspots', [])[:12]
    if not hotspots:
        return '<p class="muted">No impact hotspots in this report.</p>'
    rows = []
    for h in hotspots:
        rows.append(f"<tr><td>{_safe(h.get('label'))}</td><td>{_safe(h.get('node_type'))}</td><td>{_safe(h.get('risk_level'))}</td><td>{_safe(round((h.get('risk_score') or 0) * 100, 1))}%</td></tr>")
    return '<table><thead><tr><th>Node</th><th>Type</th><th>Risk</th><th>Score</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'


def render_html_report(payload):
    data_json = json.dumps(payload, indent=2, sort_keys=True)
    title = f"SoftGNN Report — {payload.get('project', '')}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{_safe(title)}</title>
<style>
:root {{ color-scheme: dark; --bg:#090b13; --panel:rgba(255,255,255,.075); --line:rgba(255,255,255,.14); --text:#eef3ff; --muted:#a8b3cf; --cyan:#67e8f9; --green:#86efac; --red:#fca5a5; --yellow:#fde68a; --violet:#c4b5fd; }}
* {{ box-sizing:border-box }} body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, Segoe UI, sans-serif; background:radial-gradient(circle at 20% 0%, #1d2b66 0, transparent 32%), radial-gradient(circle at 80% 10%, #4c1d95 0, transparent 30%), var(--bg); color:var(--text); }}
.wrap {{ max-width:1180px; margin:0 auto; padding:44px 24px 80px; }}
.hero {{ padding:34px; border:1px solid var(--line); border-radius:28px; background:linear-gradient(135deg, rgba(103,232,249,.14), rgba(196,181,253,.1)); box-shadow:0 24px 80px rgba(0,0,0,.35); }}
h1 {{ margin:0; font-size:42px; letter-spacing:-.04em; }} h2 {{ margin:34px 0 14px; font-size:24px; }} h3 {{ margin:14px 0 10px; }}
.tag {{ color:var(--cyan); font-weight:700; text-transform:uppercase; letter-spacing:.12em; font-size:12px; }} .muted {{ color:var(--muted); }} code {{ color:#dbeafe; background:rgba(255,255,255,.08); padding:.15rem .35rem; border-radius:7px; }}
.metrics {{ display:grid; grid-template-columns:repeat(9, minmax(100px,1fr)); gap:12px; margin-top:22px; }}
.metric {{ padding:16px; border:1px solid var(--line); border-radius:18px; background:var(--panel); backdrop-filter:blur(16px); }} .metric span {{ display:block; color:var(--muted); font-size:12px; }} .metric strong {{ display:block; font-size:28px; margin-top:8px; }}
.timeline {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; }} .step {{ padding:18px; border-radius:18px; border:1px solid var(--line); background:rgba(255,255,255,.06); }} .step b {{ color:var(--cyan); }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }} .panel {{ border:1px solid var(--line); border-radius:24px; background:var(--panel); padding:22px; overflow:hidden; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }} th,td {{ text-align:left; padding:12px; border-bottom:1px solid var(--line); vertical-align:top; }} th {{ color:var(--cyan); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
.proofs {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; }} .proof-card {{ padding:20px; border-radius:22px; border:1px solid var(--line); background:linear-gradient(180deg,rgba(255,255,255,.09),rgba(255,255,255,.045)); }} .proof-card.ok {{ border-color:rgba(134,239,172,.45); }} .proof-card.bad {{ border-color:rgba(252,165,165,.55); }}
.proof-head {{ display:flex; justify-content:space-between; gap:12px; align-items:center; color:var(--muted); }} .badge {{ padding:6px 10px; border-radius:999px; font-size:12px; font-weight:800; }} .badge.ok {{ color:#052e16; background:var(--green); }} .badge.bad {{ color:#450a0a; background:var(--red); }} .badge.skip {{ color:#422006; background:var(--yellow); }}
details {{ margin-top:20px; }} pre {{ overflow:auto; padding:18px; border-radius:18px; background:#050713; border:1px solid var(--line); color:#cbd5e1; }}
@media(max-width:900px) {{ .metrics {{ grid-template-columns:repeat(2,1fr); }} .grid,.timeline {{ grid-template-columns:1fr; }} h1{{font-size:32px}} }}
</style>
</head>
<body><main class="wrap">
<section class="hero"><div class="tag">Graph-guided · Runtime-proven · LLM-assisted</div><h1>{_safe(title)}</h1><p class="muted">Created at {_safe(payload.get('created_at'))}</p><div class="metrics">{_metric_cards(payload.get('summary', {}))}</div></section>
<h2>Workflow Timeline</h2><section class="timeline"><div class="step"><b>SCAN</b><p class="muted">Changed files and graph nodes detected.</p></div><div class="step"><b>PLAN</b><p class="muted">Coverage gaps selected as targets.</p></div><div class="step"><b>APPLY</b><p class="muted">Generated tests written and verified.</p></div><div class="step"><b>PROOF</b><p class="muted">Runtime edges confirm target execution.</p></div><div class="step"><b>REPORT</b><p class="muted">Evidence packaged for review.</p></div></section>
<section class="grid"><div class="panel"><h2>Changed Nodes</h2>{_changed_nodes(payload.get('scan', {}))}</div><div class="panel"><h2>Impact Hotspots</h2>{_impact_section(payload.get('scan', {}))}</div></section>
<h2>Generated Test Proof Cards</h2><section class="proofs">{_proof_cards(payload)}</section>
<details><summary>Raw Evidence JSON</summary><pre>{_safe(data_json)}</pre></details>
</main></body></html>"""


def save_html_report(project, payload, report_id=None):
    paths = get_project_paths(project)
    reports_dir = Path(paths['REPORTS_DIR'])
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_id = report_id or datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    report_path = reports_dir / f'{report_id}_report.html'
    latest_path = Path(paths['LATEST_REPORT_PATH'])
    html_text = render_html_report(payload)
    report_path.write_text(html_text, encoding='utf-8')
    latest_path.write_text(html_text, encoding='utf-8')
    return str(report_path), str(latest_path)


def latest_report_path(project):
    return str(get_project_paths(project)['LATEST_REPORT_PATH'])
