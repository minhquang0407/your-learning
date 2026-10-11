import contextlib
import io
import json
import os
import subprocess
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from softgnn_advisor.core.dashboard_assets import DASHBOARD_HTML
from softgnn_advisor.core.graph_exporter import export_graph


JOBS = {}
ALLOWED_ACTIONS = {'refresh', 'scan', 'pr_scan', 'impact', 'map_runtime', 'generate', 'generate_file', 'generate_target', 'open_report'}


def _git(repo_path, args):
    try:
        result = subprocess.run(['git'] + args, cwd=repo_path, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        return result.stdout.strip()
    except Exception:
        return ''


def _status(project, repo_path):
    return {
        'project': project,
        'repo_path': os.path.abspath(repo_path),
        'branch': _git(repo_path, ['branch', '--show-current']),
        'head': _git(repo_path, ['rev-parse', '--short', 'HEAD']),
    }


def _run_cli_action(project, repo_path, payload):
    from softgnn_advisor.core.pr_scanner import PRScanner
    from softgnn_advisor.core.test_generation_agent import TestGenerationAgent
    from softgnn_advisor.scripts.etl_run import run_etl_pipeline
    from softgnn_advisor.core.change_provider import build_filesystem_snapshot, save_filesystem_snapshot, snapshot_path_for_project
    action = payload.get('action')
    if action == 'refresh':
        run_etl_pipeline(repo_path, project)
        save_filesystem_snapshot(snapshot_path_for_project(project), build_filesystem_snapshot(repo_path))
        print('Refresh complete.')
    elif action in {'scan', 'pr_scan'}:
        result = PRScanner(project, repo_path=repo_path).scan(base=payload.get('base', 'main'), head=payload.get('head', 'HEAD'), change_source=payload.get('change_source', 'auto'))
        print(f'Changed files: {len(result.changed_files)}')
        print(f'Changed nodes: {len(result.changed_nodes)}')
        print(f'Missing coverage: {len(result.missing_coverage)}')
        for warning in result.warnings[:10]:
            print('WARNING:', warning)
    elif action == 'impact':
        from softgnn_advisor.core.impact_engine import ImpactEngine, ImpactTarget
        target = payload.get('target')
        engine = ImpactEngine(project)
        key = engine.key_by_full_id.get(target)
        if not key:
            print(f'Target not found: {target}')
            return
        result = engine.analyze(ImpactTarget(key, target, key[0]), mode='hybrid', limit=20)
        for c in result.candidates[:20]:
            print(f'{c.label} [{c.node_type}] {c.final_score:.2f} evidence={c.tiers}')
    elif action == 'map_runtime':
        from softgnn_advisor.infrastructure.pipelines.runtime_coverage_mapper import RuntimeCoverageMapper
        result = RuntimeCoverageMapper(project, repo_path=repo_path).map_runtime_coverage(pytest_args=payload.get('pytest', 'tests'), mode='per-test', persist=True)
        print(f'Runtime edges: {len(result.runtime_edges)}')
    elif action in {'generate', 'generate_file', 'generate_target'}:
        agent = TestGenerationAgent(project, repo_path=repo_path)
        scan = PRScanner(project, repo_path=repo_path).scan(base=payload.get('base', 'main'), head=payload.get('head', 'HEAD'), change_source=payload.get('change_source', 'auto'))
        result = agent.plan_from_scan(
            scan,
            mode='patch',
            max_targets=int(payload.get('max_targets', 1)),
            target_id=payload.get('target') if action == 'generate_target' else payload.get('target'),
            source_file=payload.get('source_file'),
            only_file=payload.get('only_file') if action == 'generate_file' else payload.get('only_file'),
            verify=True,
            repair_iters=1,
            refresh_runtime=True,
            runtime_mode='per-test',
            pytest_args=payload.get('pytest'),
            generation_strategy=payload.get('strategy', 'template'),
            llm_required=False,
            change_source=payload.get('change_source', 'auto'),
        )
        print(f'Plans: {len(result.plans)}')
        print(f'Files written: {len(result.files_written)}')
        for warning in result.warnings[:20]:
            print('WARNING:', warning)
    elif action == 'open_report':
        from softgnn_advisor.config.settings import get_project_paths
        path = get_project_paths(project)['LATEST_REPORT_PATH']
        webbrowser.open(path.resolve().as_uri())
        print(f'Opened {path}')


def _start_job(project, repo_path, payload):
    action = payload.get('action')
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f'Action not allowed: {action}')
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {'done': False, 'logs': '', 'started_at': time.time(), 'action': action}

    def worker():
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                _run_cli_action(project, repo_path, payload)
            JOBS[job_id]['logs'] = buf.getvalue()
            JOBS[job_id]['done'] = True
            JOBS[job_id]['ok'] = True
        except Exception as exc:
            JOBS[job_id]['logs'] = buf.getvalue() + f'\nERROR: {exc}'
            JOBS[job_id]['done'] = True
            JOBS[job_id]['ok'] = False

    threading.Thread(target=worker, daemon=True).start()
    return job_id


def make_handler(project, repo_path):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, data, status=200):
            raw = json.dumps(data, default=str).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == '/':
                raw = DASHBOARD_HTML.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            elif parsed.path == '/api/graph':
                qs = parse_qs(parsed.query)
                self._json(export_graph(project, focus=(qs.get('focus') or [None])[0], target=(qs.get('target') or [None])[0], depth=int((qs.get('depth') or [1])[0]), max_nodes=int((qs.get('max_nodes') or [500])[0])))
            elif parsed.path == '/api/status':
                self._json(_status(project, repo_path))
            elif parsed.path.startswith('/api/jobs/'):
                job_id = parsed.path.rsplit('/', 1)[-1]
                self._json(JOBS.get(job_id, {'done': True, 'logs': 'Job not found', 'ok': False}), status=200 if job_id in JOBS else 404)
            else:
                self._json({'error': 'not found'}, status=404)

        def do_POST(self):
            if self.path != '/api/action':
                self._json({'error': 'not found'}, status=404)
                return
            length = int(self.headers.get('Content-Length') or 0)
            payload = json.loads(self.rfile.read(length).decode('utf-8') or '{}')
            try:
                job_id = _start_job(project, repo_path, payload)
                self._json({'job_id': job_id})
            except Exception as exc:
                self._json({'error': str(exc)}, status=400)

        def log_message(self, fmt, *args):
            return

    return Handler


def start_dashboard(project, repo_path, host='127.0.0.1', port=8765, open_browser=False):
    server = ThreadingHTTPServer((host, int(port)), make_handler(project, repo_path))
    url = f'http://{host}:{port}'
    print(f'SoftGNN dashboard running at {url}')
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('Dashboard stopped.')
