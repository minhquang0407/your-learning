import ast
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from softgnn_advisor.core.pr_scanner import PRScanner
from softgnn_advisor.core.llm_provider import LLMRequest, build_llm_provider, load_llm_config
from softgnn_advisor.core.llm_test_schema import parse_generated_test, parse_repair_response
from softgnn_advisor.infrastructure.pipelines.runtime_coverage_mapper import RuntimeCoverageMapper


@dataclass
class TestGenerationTarget:
    node_id: str
    source_file: str
    reason: str
    priority: float
    evidence: list = field(default_factory=list)
    suggested_file: str = ''


@dataclass
class GeneratedTestPlan:
    target_id: str
    test_file: str
    test_names: list
    rationale: str
    code: str
    assumptions: list = field(default_factory=list)
    source_file: str = ''


@dataclass
class PytestFailure:
    test_name: str
    error_type: str
    message: str
    traceback: str


@dataclass
class RepairAttempt:
    iteration: int
    action: str
    pytest_returncode: int
    pytest_output: str


@dataclass
class PlanVerificationResult:
    target_id: str
    test_file: str
    pytest_target: str
    returncode: int | None
    output: str
    status: str
    repair_attempts: list = field(default_factory=list)
    # M4: runtime proof
    proof_status: str = 'skipped'   # 'pass', 'fail', 'skipped'
    proof_edges: list = field(default_factory=list)
    proof_message: str = ''


@dataclass
class TestGenerationResult:
    targets: list
    plans: list
    files_written: list
    pytest_returncode: int | None
    pytest_output: str
    warnings: list
    mode: str
    failures: list = field(default_factory=list)
    repair_attempts: list = field(default_factory=list)
    rolled_back: bool = False
    runtime_result: object | None = None
    post_scan: object | None = None
    pre_missing_coverage_count: int = 0
    post_missing_coverage_count: int | None = None
    verification_results: list = field(default_factory=list)
    apply_run_path: str | None = None
    apply_run_id: str | None = None


class TestGenerationAgent:
    def __init__(self, project, repo_path=None, llm_provider=None, llm_model=None, llm_base_url=None, llm_api_key=None, llm_timeout=None):
        self.project = project
        self.scanner = PRScanner(project, repo_path=repo_path)
        self.repo_path = os.path.abspath(repo_path or self.scanner.repo_path)
        self.llm_config = load_llm_config(provider=llm_provider, base_url=llm_base_url, model=llm_model, api_key=llm_api_key, timeout=llm_timeout)
        self.llm_provider = build_llm_provider(self.llm_config)

    def generate(self, base='main', head='HEAD', mode='plan', max_targets=3, verify=True, repair_iters=0, target_id=None, source_file=None, refresh_runtime=None, runtime_mode='auto', confirm_pr_scan=True, keep_failing_tests=False, pytest_args=None, generation_strategy='auto', llm_required=False, llm_temperature=0.1, llm_max_tokens=4096, change_source='auto', partial_rollback=True, pytest_stream=True, failure_feedback=None):
        if mode not in ('plan', 'patch'):
            raise ValueError("mode must be 'plan' or 'patch'")
        if generation_strategy not in ('template', 'llm', 'auto'):
            raise ValueError("generation_strategy must be one of: template, llm, auto")
        scan = self.scanner.scan(base=base, head=head, mode='deterministic', max_impact=20, suggest_tests=True, change_source=change_source)
        return self.plan_from_scan(
            scan,
            mode=mode,
            base=base,
            head=head,
            max_targets=max_targets,
            verify=verify,
            repair_iters=repair_iters,
            target_id=target_id,
            source_file=source_file,
            refresh_runtime=refresh_runtime,
            runtime_mode=runtime_mode,
            confirm_pr_scan=confirm_pr_scan,
            keep_failing_tests=keep_failing_tests,
            pytest_args=pytest_args,
            generation_strategy=generation_strategy,
            llm_required=llm_required,
            llm_temperature=llm_temperature,
            llm_max_tokens=llm_max_tokens,
            change_source=change_source,
            partial_rollback=partial_rollback,
            pytest_stream=pytest_stream,
            failure_feedback=failure_feedback,
        )

    def plan_from_scan(self, scan, mode='plan', base='main', head='HEAD', max_targets=3, verify=True, repair_iters=0, target_id=None, source_file=None, only_file=None, refresh_runtime=None, runtime_mode='auto', confirm_pr_scan=False, keep_failing_tests=False, pytest_args=None, generation_strategy='auto', llm_required=False, llm_temperature=0.1, llm_max_tokens=4096, change_source='auto', partial_rollback=True, pytest_stream=True, failure_feedback=None):
        if mode not in ('plan', 'patch'):
            raise ValueError("mode must be 'plan' or 'patch'")
        if generation_strategy not in ('template', 'llm', 'auto'):
            raise ValueError("generation_strategy must be one of: template, llm, auto")
        warnings = []
        pre_missing_count = len(scan.missing_coverage)
        if target_id:
            if not source_file:
                source_file = self._infer_source_file(target_id, scan)
            if not source_file:
                raise ValueError('source_file is required when target_id cannot be resolved from PR scan')
            targets = [TestGenerationTarget(target_id, source_file, 'explicit target override', 999.0, ['explicit user/CLI target'], self._suggest_test_file(source_file))]
        else:
            targets = self._rank_targets(scan, warnings)
            if only_file:
                normalized = only_file.replace('\\', '/').strip('/')
                targets = [t for t in targets if (t.source_file or '').replace('\\', '/').strip('/') == normalized]
                if not targets:
                    warnings.append(f'No generation targets found in {normalized} for the current scan.')
            targets = targets[:max_targets]
        plans = [self._build_plan(target, generation_strategy, warnings, llm_required, llm_temperature, llm_max_tokens, failure_feedback=failure_feedback) for target in targets]
        files_written = []
        pytest_returncode = None
        pytest_output = ''
        failures = []
        repair_attempts = []
        verification_results = []
        rolled_back = False
        runtime_result = None
        post_scan = None
        post_missing_count = None
        if refresh_runtime is None:
            refresh_runtime = mode == 'patch' and verify
        if mode == 'patch' and plans:
            snapshots = self._snapshot_plans(plans)
            files_written = self._apply_plans(plans, warnings)
            if verify and files_written:
                verification_results, kept_files, pytest_returncode, pytest_output, failures, repair_attempts, rolled_back = self._verify_written_plans(
                    plans,
                    snapshots,
                    warnings,
                    repair_iters=repair_iters,
                    keep_failing_tests=keep_failing_tests,
                    pytest_args=pytest_args,
                    generation_strategy=generation_strategy,
                    llm_required=llm_required,
                    llm_temperature=llm_temperature,
                    llm_max_tokens=llm_max_tokens,
                    partial_rollback=partial_rollback,
                    pytest_stream=pytest_stream,
                )
                files_written = kept_files
                if kept_files and refresh_runtime:
                    runtime_args = pytest_args or ' '.join(kept_files)
                    runtime_result = RuntimeCoverageMapper(self.project, repo_path=self.repo_path).map_runtime_coverage(pytest_args=runtime_args, mode=runtime_mode, persist=True)
                    if confirm_pr_scan:
                        post_scan = self.scanner.scan(base=base, head=head, mode='deterministic', max_impact=20, suggest_tests=True, change_source=change_source)
                        post_missing_count = len(post_scan.missing_coverage)
        return TestGenerationResult(targets, plans, files_written, pytest_returncode, pytest_output, warnings + scan.warnings, mode, failures, repair_attempts, rolled_back, runtime_result, post_scan, pre_missing_count, post_missing_count, verification_results)

    def _rank_targets(self, scan, warnings=None):
        warnings = warnings if warnings is not None else []
        changed_by_id = {node.full_id: node for node in scan.changed_nodes}
        contract_by_id = {change.function_id: change for change in scan.contract_changes}
        hotspot_labels = {h.label: h for h in scan.impact_hotspots}
        suggestions = {cover: suggestion for suggestion in scan.suggested_tests for cover in suggestion.covers}
        targets = []
        skipped_side_effects = []
        for gap in scan.missing_coverage:
            node = changed_by_id.get(gap.target_id)
            if not node or node.node_type != 'Function':
                continue
            if self._is_risky_entrypoint_target(node):
                skipped_side_effects.append(f'{gap.target_id} ({node.source_file})')
                continue
            priority = 100.0
            evidence = [gap.reason]
            contract = contract_by_id.get(gap.target_id)
            if contract:
                if contract.signature_changed or contract.return_pattern_changed:
                    priority += 80
                elif contract.behavior_changed:
                    priority += 50
                elif contract.source_only_changed:
                    priority += 20
                evidence.extend(contract.summary)
            if 'no runtime' in gap.reason:
                priority += 60
            if 'no runtime or static' in gap.reason:
                priority += 40
            if node.label in hotspot_labels:
                priority += 30
                evidence.append('high impact hotspot')
            suggested_file = suggestions.get(gap.target_id).suggested_file if gap.target_id in suggestions else self._suggest_test_file(node.source_file)
            targets.append(TestGenerationTarget(gap.target_id, node.source_file, gap.reason, priority, evidence, suggested_file))
        if skipped_side_effects:
            warnings.append('Skipped import-time side-effect target(s): ' + '; '.join(skipped_side_effects) + '. These look like Streamlit/app entrypoints and are safer to test after refactoring UI/runtime code behind a function or guard.')
            for skipped in skipped_side_effects:
                self._print_status('SKIP', f'Import-time side-effect target: {skipped}', 'magenta')
        targets.sort(key=lambda t: t.priority, reverse=True)
        return targets

    def _is_risky_entrypoint_target(self, node):
        source_file = (getattr(node, 'source_file', '') or '').replace('\\', '/')
        if not source_file:
            return False
        basename = os.path.basename(source_file)
        if basename not in {'main.py', 'app.py', 'streamlit_app.py'}:
            return False
        try:
            text = Path(self.repo_path, source_file).read_text(encoding='utf-8', errors='ignore')
        except OSError:
            return False
        return self._has_import_time_side_effects(text)

    def _has_import_time_side_effects(self, text):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return False
        risky_modules = {'streamlit'}
        streamlit_aliases = set()
        risky_imports = False
        for stmt in tree.body:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    root = alias.name.split('.', 1)[0]
                    if root in risky_modules:
                        streamlit_aliases.add(alias.asname or root)
                        risky_imports = True
            elif isinstance(stmt, ast.ImportFrom):
                root = (stmt.module or '').split('.', 1)[0]
                if root in risky_modules:
                    risky_imports = True
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                continue
            if self._node_calls_name(stmt, {'init_system', 'run_ingestion_pipeline'}):
                return True
            if streamlit_aliases and self._node_uses_streamlit_call(stmt, streamlit_aliases):
                return True
        return risky_imports and any(not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign)) for stmt in tree.body)

    def _node_calls_name(self, node, names):
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name) and func.id in names:
                    return True
                if isinstance(func, ast.Attribute) and func.attr in names:
                    return True
        return False

    def _node_uses_streamlit_call(self, node, aliases):
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in aliases:
                    return True
        return False

    def _infer_source_file(self, target_id, scan):
        for node in scan.changed_nodes:
            if node.full_id == target_id:
                return node.source_file
        return None

    def _build_plan(self, target, generation_strategy='template', warnings=None, llm_required=False, llm_temperature=0.1, llm_max_tokens=4096, failure_feedback=None):
        warnings = warnings if warnings is not None else []
        context = self._collect_source_context(target)
        if generation_strategy in ('llm', 'auto'):
            llm_plan = self._try_build_llm_plan(target, context, warnings, llm_required, llm_temperature, llm_max_tokens, failure_feedback=failure_feedback)
            if llm_plan:
                return llm_plan
        function_name = target.node_id.replace('FUNC:', '')
        test_name = f"test_{self._safe_name(function_name)}_semantic"
        test_file = target.suggested_file or self._suggest_test_file(target.source_file)
        code, assumptions = self._generate_semantic_pytest_code(target, context, test_name)
        rationale = f"Generated semantic test because {target.node_id} has missing coverage: {target.reason}."
        return GeneratedTestPlan(target.node_id, test_file, [test_name], rationale, code, assumptions, target.source_file)

    def _try_build_llm_plan(self, target, context, warnings, llm_required, llm_temperature, llm_max_tokens, failure_feedback=None):
        if not getattr(self.llm_provider, 'available', False):
            message = 'LLM provider not configured; falling back to template generation.'
            if llm_required:
                raise RuntimeError(message)
            warnings.append(message)
            return None
        request = LLMRequest(
            system_prompt=self._llm_generation_system_prompt(),
            user_prompt=self._llm_generation_user_prompt(target, context, failure_feedback=failure_feedback),
            temperature=llm_temperature,
            max_tokens=llm_max_tokens,
        )
        try:
            response = self.llm_provider.complete(request)
            generated = parse_generated_test(response.text)
        except Exception as exc:
            message = f'LLM generation failed; falling back to template generation: {exc}'
            if llm_required:
                raise RuntimeError(message) from exc
            warnings.append(message)
            return None
        return GeneratedTestPlan(
            target.node_id,
            generated.test_file,
            generated.test_names,
            generated.rationale,
            generated.code,
            generated.assumptions,
            target.source_file,
        )

    def _llm_generation_system_prompt(self):
        return """You are SoftGNN's test generation assistant. Generate concise, deterministic pytest tests only. Return exactly one JSON object and no markdown. Never modify production code. Tests must write only under tmp_path if file IO is needed. Use the provided source context exactly: do not invent constructor argument names, method names, imports, or return shapes. If a module has import-time side effects, avoid importing it until mocks are installed or mock dependency modules via sys.modules first. Mock heavy dependencies, training loops, GPU/CUDA, network, databases, Streamlit runtime, and external services."""

    def _llm_generation_user_prompt(self, target, context, failure_feedback=None):
        existing_tests = self._read_text(os.path.join(self.repo_path, (target.suggested_file or self._suggest_test_file(target.source_file)).replace('/', os.sep)))
        qualname = target.node_id.replace('FUNC:', '')
        snippet = self._target_source_snippet(qualname, context)
        focused_context = self._focused_source_context(qualname, context)
        feedback_text = self._format_failure_feedback(target.node_id, failure_feedback)
        return f"""
Return JSON with this schema:
{{
  "test_file": "tests/test_*.py",
  "test_names": ["test_name"],
  "code": "pytest code as a string",
  "rationale": "why this test matters",
  "assumptions": ["assumption"],
  "requires": ["pytest"]
}}

Target id: {target.node_id}
Source file: {target.source_file}
Missing coverage reason: {target.reason}
Evidence: {'; '.join(target.evidence) if target.evidence else '-'}
Suggested test file: {target.suggested_file or self._suggest_test_file(target.source_file)}
Module path: {context['module_path']}

Target source snippet:
```python
{snippet[:6000]}
```

Focused source context, including containing class, constructor, nearby signatures, and import-time side effects:
```python
{focused_context[:10000]}
```

Relevant imports:
```python
{chr(10).join(context.get('imports', []))[:2000]}
```

Detected call/dependency names inside target: {', '.join(context.get('target_calls', [])) or '-'}

Existing tests in suggested file:
```python
{existing_tests[-6000:] if existing_tests else '# no existing tests'}
```

Failure feedback from previous apply attempt, if any:
```text
{feedback_text}
```

Constraints:
- Return JSON only.
- test_file must be under tests/.
- code must define at least one pytest function listed in test_names.
- Prefer behavior assertions over callable/hasattr smoke tests.
- Use monkeypatch/tmp_path for side effects.
- Mock heavy training, CUDA, network, databases, Streamlit runtime, and filesystem writes outside tmp_path.
- Do not use subprocess, requests, urllib, socket, os.system, or shutil.rmtree.
- Use real constructor signatures and real method names from focused context.
- If testing a module with import-time side effects, install mocks before importing the module under test.
- Multi-line `with` statements must use parentheses, e.g. `with (patch(...), patch(...)):`; never leave a line ending in a bare comma.
""".strip()

    def _format_failure_feedback(self, target_id, failure_feedback):
        if not failure_feedback:
            return '-'
        item = failure_feedback.get(target_id) if isinstance(failure_feedback, dict) else None
        if not item:
            return '-'
        parts = [
            'Previous generated test for this target failed during apply.',
            f"Status: {item.get('status', '-')}",
            f"Test file: {item.get('test_file', '-')}",
            f"Repair attempts: {item.get('repair_attempts', 0)}",
        ]
        previous_code = item.get('previous_generated_code') or item.get('last_generated_code') or ''
        pytest_output = item.get('pytest_output_tail') or item.get('pytest_output') or ''
        if previous_code:
            parts.append('Previous generated code:')
            parts.append(previous_code[-4000:])
        if pytest_output:
            parts.append('Pytest failure output:')
            parts.append(pytest_output[-4000:])
        parts.append('Generate a revised test that avoids repeating the previous failure.')
        return '\n'.join(parts)

    def _target_source_snippet(self, qualname, context):
        parts = qualname.split('.')
        if len(parts) >= 2:
            class_name, method_name = parts[-2], parts[-1]
            cls = context.get('classes', {}).get(class_name, {})
            method = cls.get('methods', {}).get(method_name)
            if method:
                return method.get('source', '')
            return cls.get('source', '')
        fn = context.get('functions', {}).get(parts[-1])
        return fn.get('source', '') if fn else context.get('source', '')[:4000]

    def _collect_source_context(self, target):
        source_path = os.path.join(self.repo_path, target.source_file.replace('/', os.sep))
        source = self._read_text(source_path)
        context = {
            'source': source,
            'imports': self._extract_imports(source),
            'classes': {},
            'functions': {},
            'module_path': self._module_path(target.source_file),
            'module_side_effects': [],
            'target_calls': [],
        }
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return context
        lines = source.splitlines()
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                methods = {}
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods[child.name] = {
                            'signature': self._signature(child),
                            'source': self._slice_source(lines, child),
                        }
                context['classes'][node.name] = {
                    'source': self._slice_source(lines, node),
                    'methods': methods,
                }
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                context['functions'][node.name] = {
                    'signature': self._signature(node),
                    'source': self._slice_source(lines, node),
                }
        context['module_side_effects'] = self._detect_module_side_effects(tree, lines)
        qualname = target.node_id.replace('FUNC:', '')
        context['target_calls'] = self._target_call_names(qualname, context)
        return context

    def _focused_source_context(self, qualname, context):
        sections = []
        if context.get('imports'):
            sections.append('# Module imports\n' + '\n'.join(context.get('imports', [])))
        if context.get('module_side_effects'):
            sections.append('# Potential import-time side effects\n' + '\n'.join(context.get('module_side_effects', [])))
        parts = qualname.split('.')
        if len(parts) >= 2:
            class_name, method_name = parts[-2], parts[-1]
            cls = context.get('classes', {}).get(class_name)
            if cls:
                methods = cls.get('methods', {})
                if '__init__' in methods:
                    sections.append(f"# Constructor signature for {class_name}\n{methods['__init__'].get('source', '')}")
                if method_name in methods and method_name != '__init__':
                    sections.append(f"# Target method source for {class_name}.{method_name}\n{methods[method_name].get('source', '')}")
                other_sigs = [f"def {name}{'' if meta.get('signature', '').startswith('(') else ' '}{meta.get('signature', '')}" for name, meta in methods.items() if name not in {'__init__', method_name}]
                if other_sigs:
                    sections.append('# Other method signatures in containing class\n' + '\n'.join(other_sigs[:40]))
                sections.append(f"# Containing class source for {class_name}\n{cls.get('source', '')}")
        else:
            fn = context.get('functions', {}).get(parts[-1])
            if fn:
                sections.append(f"# Target function source for {parts[-1]}\n{fn.get('source', '')}")
        if context.get('functions'):
            signatures = [meta.get('signature', '') for meta in context.get('functions', {}).values()]
            sections.append('# Module-level function signatures\n' + '\n'.join(signatures[:40]))
        return '\n\n'.join(s for s in sections if s)

    def _detect_module_side_effects(self, tree, lines):
        effects = []
        safe_nodes = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        for node in getattr(tree, 'body', []):
            if isinstance(node, safe_nodes):
                continue
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.Expr)):
                text = self._slice_source(lines, node).strip()
                if '(' in text or any(name in text for name in ('streamlit', 'st.', 'Qdrant', 'connect', 'init_system')):
                    effects.append(text[:300])
            else:
                effects.append(self._slice_source(lines, node).strip()[:300])
        return effects

    def _target_call_names(self, qualname, context):
        source = self._target_source_snippet(qualname, context)
        if not source:
            return []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    names.append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    names.append(node.func.attr)
        return sorted(set(names))

    def _generate_semantic_pytest_code(self, target, context, test_name):
        qualname = target.node_id.replace('FUNC:', '')
        module_path = context['module_path']
        if qualname.startswith('HGTLinkPrediction.') or qualname == 'HGTLinkPrediction':
            return self._hgt_link_prediction_template(module_path), [
                'Uses tiny heterogeneous metadata to avoid full training/data loading.',
                'Validates constructor behavior, decoder filtering, and missing metadata error path.',
            ]
        if qualname.startswith('HGTEncoder.') or qualname == 'HGTEncoder':
            return self._hgt_encoder_template(module_path), [
                'Uses an empty convolution stack to isolate projection/dropout behavior.',
                'Validates output keys, shapes, and ReLU non-negativity with tiny tensors.',
            ]
        if qualname.startswith('InteractionMLP.') or qualname == 'InteractionMLP':
            return self._interaction_mlp_template(module_path), [
                'Uses tiny source/destination embeddings.',
                'Validates decoder returns one score per edge pair.',
            ]
        if qualname == 'train_one_config':
            return self._train_one_config_template(module_path), [
                'Mocks model construction, train/evaluate callbacks, AMP scaler, CUDA cleanup, and file writes.',
                'Runs a one-epoch CPU-safe path to validate config usage and return contract without full training.',
            ]
        return self._fallback_semantic_template(target, context, test_name), [
            'Fallback semantic smoke test based on importability/callability.',
            'Manual refinement may be needed for complex side effects or required fixtures.',
        ]

    def _hgt_link_prediction_template(self, module_path):
        return f'''"""Semantic tests generated by SoftGNN M3."""

import pytest

from {module_path} import HGTEncoder, HGTLinkPrediction


def test_hgt_link_prediction_initializes_metadata_encoder_and_decoders():
    metadata = (
        ["user", "post"],
        [
            ("user", "writes", "post"),
            ("post", "rev_writes", "user"),
        ],
    )

    model = HGTLinkPrediction(
        hidden_channels=8,
        out_channels=1,
        metadata=metadata,
        dropout=0.0,
        num_heads=2,
        num_layers=1,
    )

    assert model.metadata == metadata
    assert isinstance(model.encoder, HGTEncoder)
    assert set(model.lin_dict.keys()) == {{"user", "post"}}
    assert len(model.convs) == 1
    assert "__writes__" in model.decoders
    assert "__rev_writes__" not in model.decoders


def test_hgt_link_prediction_requires_data_or_metadata():
    with pytest.raises(ValueError, match="data.*metadata"):
        HGTLinkPrediction(hidden_channels=8, out_channels=1)
'''

    def _hgt_encoder_template(self, module_path):
        return f'''"""Semantic tests generated by SoftGNN M3."""

import torch
from torch import nn

from {module_path} import HGTEncoder


def test_hgt_encoder_forward_projects_each_node_type_without_convs():
    lin_dict = nn.ModuleDict({{
        "user": nn.Linear(3, 4),
        "post": nn.Linear(2, 4),
    }})
    dropout = nn.Dropout(p=0.0)
    encoder = HGTEncoder(hidden_channels=4, lin_dict=lin_dict, convs=nn.ModuleList(), dropout=dropout)

    x_dict = {{
        "user": torch.randn(2, 3),
        "post": torch.randn(3, 2),
    }}

    out = encoder(x_dict, edge_index_dict={{}})

    assert set(out.keys()) == {{"user", "post"}}
    assert out["user"].shape == (2, 4)
    assert out["post"].shape == (3, 4)
    assert torch.all(out["user"] >= 0)
    assert torch.all(out["post"] >= 0)
'''

    def _interaction_mlp_template(self, module_path):
        return f'''"""Semantic tests generated by SoftGNN M3."""

import torch

from {module_path} import InteractionMLP


def test_interaction_mlp_returns_one_score_per_pair():
    model = InteractionMLP(input_dim=4, hidden_dim=8, output_dim=1, dropout=0.0)
    z_src = torch.randn(3, 4)
    z_dst = torch.randn(3, 4)

    out = model(z_src, z_dst)

    assert out.shape == (3,)
    assert out.dtype == z_src.dtype
'''

    def _train_one_config_template(self, module_path):
        return f'''"""Semantic tests generated by SoftGNN M3."""

import json
from pathlib import Path
from unittest.mock import Mock

import torch

import {module_path} as train_model


class _TinyTrainData:
    def __init__(self):
        self.metadata_called = False

    def metadata(self):
        self.metadata_called = True
        return (["user"], [])


class _TinyModel(torch.nn.Module):
    def __init__(self, hidden_dim, output_dim, data, dropout):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.data = data
        self.dropout = dropout
        self.weight = torch.nn.Parameter(torch.tensor(1.0))

    def forward(self, *args, **kwargs):
        return self.weight.reshape(1)


class _NoOpScheduler:
    def __init__(self, *args, **kwargs):
        self.step_calls = 0

    def step(self):
        self.step_calls += 1


def test_train_one_config_uses_config_and_returns_training_contract(monkeypatch, tmp_path):
    train_data = _TinyTrainData()
    val_data = object()
    test_data = object()
    target_edge_types = [("user", "follows", "user")]
    split_data = (train_data, val_data, test_data, target_edge_types)
    config = {{
        "hidden_dim": 4,
        "lr": 0.01,
        "epochs": 1,
        "batch_size": 2,
        "dropout": 0.25,
    }}
    created_models = []

    def fake_model(hidden_dim, output_dim, data, dropout):
        model = _TinyModel(hidden_dim, output_dim, data, dropout)
        created_models.append(model)
        return model

    monkeypatch.setattr(train_model, "HGTLinkPrediction", fake_model)
    monkeypatch.setattr(train_model, "train_epoch", lambda *args, **kwargs: 0.125)
    monkeypatch.setattr(train_model, "evaluate", lambda *args, **kwargs: 0.75)
    monkeypatch.setattr(train_model, "call_back", Mock())
    monkeypatch.setattr(train_model.torch.optim.lr_scheduler, "CosineAnnealingWarmRestarts", _NoOpScheduler)
    monkeypatch.setattr(train_model.torch.amp, "GradScaler", lambda *args, **kwargs: Mock())
    monkeypatch.setattr(train_model.torch.cuda, "empty_cache", Mock())
    monkeypatch.setattr(train_model.gc, "collect", Mock(return_value=0))
    history_path = tmp_path / "history.json"
    monkeypatch.setattr(train_model, "TRAINING_HISTORY_PATH", history_path)

    best_val_auc, final_test_auc, best_model = train_model.train_one_config(
        split_data,
        config,
        torch.device("cpu"),
    )

    assert best_val_auc == 0.75
    assert final_test_auc == 1.0
    assert best_model is created_models[0]
    assert created_models[0].hidden_dim == config["hidden_dim"]
    assert created_models[0].dropout == config["dropout"]
    assert history_path.exists()
    history = json.loads(Path(history_path).read_text(encoding="utf-8"))
    assert history["epoch"] == [1]
    assert history["loss"] == [0.125]
    assert history["val_auc"] == [0.75]
    train_model.call_back.assert_called_once_with(created_models[0])
'''

    def _fallback_semantic_template(self, target, context, test_name):
        module_path = context['module_path']
        qualname = target.node_id.replace('FUNC:', '')
        parts = qualname.split('.')
        if len(parts) >= 2:
            class_name, method_name = parts[-2], parts[-1]
            return f'''"""Semantic smoke tests generated by SoftGNN M3."""

from {module_path} import {class_name}


def {test_name}():
    assert hasattr({class_name}, "{method_name}")
'''
        fn_name = parts[-1]
        return f'''"""Semantic smoke tests generated by SoftGNN M3."""

from {module_path} import {fn_name}


def {test_name}():
    assert callable({fn_name})
'''

    def apply_saved_plans(self, plans, base='main', head='HEAD', verify=True, repair_iters=2, refresh_runtime=True, runtime_mode='per-test', confirm_pr_scan=True, keep_failing_tests=False, pytest_args=None, generation_strategy='auto', llm_required=False, llm_temperature=0.1, llm_max_tokens=4096, change_source='auto', partial_rollback=True, pytest_stream=True, require_runtime_proof=True):
        warnings = []
        files_written = []
        pytest_returncode = None
        pytest_output = ''
        failures = []
        repair_attempts = []
        rolled_back = False
        runtime_result = None
        post_scan = None
        post_missing_count = None
        verification_results = []
        snapshots = self._snapshot_plans(plans)
        files_written = self._apply_plans(plans, warnings)
        if verify and files_written:
            verification_results, kept_files, pytest_returncode, pytest_output, failures, repair_attempts, rolled_back = self._verify_written_plans(
                plans,
                snapshots,
                warnings,
                repair_iters=repair_iters,
                keep_failing_tests=keep_failing_tests,
                pytest_args=pytest_args,
                generation_strategy=generation_strategy,
                llm_required=llm_required,
                llm_temperature=llm_temperature,
                llm_max_tokens=llm_max_tokens,
                partial_rollback=partial_rollback,
                pytest_stream=pytest_stream,
                require_runtime_proof=(require_runtime_proof and refresh_runtime),
            )
            files_written = kept_files
            if kept_files and refresh_runtime:
                runtime_args = pytest_args or ' '.join(kept_files)
                runtime_result = RuntimeCoverageMapper(self.project, repo_path=self.repo_path).map_runtime_coverage(pytest_args=runtime_args, mode=runtime_mode, persist=True)
                if confirm_pr_scan:
                    post_scan = self.scanner.scan(base=base, head=head, mode='deterministic', max_impact=20, suggest_tests=True, change_source=change_source)
                    post_missing_count = len(post_scan.missing_coverage)
        result = TestGenerationResult([], plans, files_written, pytest_returncode, pytest_output, warnings, 'patch', failures, repair_attempts, rolled_back, runtime_result, post_scan, 0, post_missing_count, verification_results)
        if verification_results:
            run_path, run_id = self._persist_apply_run(result)
            result.apply_run_path = run_path
            result.apply_run_id = run_id
        return result

    def _apply_plans(self, plans, warnings):
        written = []
        for plan in plans:
            rel_path = plan.test_file.replace('\\', '/')
            if not rel_path.startswith('tests/'):
                rel_path = 'tests/' + os.path.basename(rel_path)
            abs_path = os.path.join(self.repo_path, rel_path.replace('/', os.sep))
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            marked_code = self._wrap_generated_block(plan)
            if os.path.exists(abs_path):
                existing = self._read_text(abs_path)
                duplicate_names = [name for name in self._test_function_names(plan.code) if f'def {name}(' in existing]
                if duplicate_names:
                    warnings.append(f'Skipped {rel_path}; generated test(s) already exist: {", ".join(duplicate_names)}.')
                    continue
                content = existing.rstrip() + '\n\n\n' + marked_code
            else:
                content = marked_code
            Path(abs_path).write_text(content, encoding='utf-8')
            written.append(rel_path)
        return sorted(set(written))

    def _snapshot_plans(self, plans):
        snapshots = {}
        for plan in plans:
            rel_path = plan.test_file.replace('\\', '/')
            if not rel_path.startswith('tests/'):
                rel_path = 'tests/' + os.path.basename(rel_path)
            abs_path = os.path.join(self.repo_path, rel_path.replace('/', os.sep))
            snapshots[abs_path] = self._read_text(abs_path) if os.path.exists(abs_path) else None
        return snapshots

    def _rollback_snapshots(self, snapshots):
        for abs_path, content in snapshots.items():
            if content is None:
                if os.path.exists(abs_path):
                    os.remove(abs_path)
            else:
                Path(abs_path).write_text(content, encoding='utf-8')

    def _wrap_generated_block(self, plan):
        return (
            f'# <softgnn-generated target="{plan.target_id}" start>\n'
            f'{plan.code.rstrip()}\n'
            f'# <softgnn-generated target="{plan.target_id}" end>\n'
        )

    def _plan_rel_path(self, plan):
        rel_path = plan.test_file.replace('\\', '/')
        if not rel_path.startswith('tests/'):
            rel_path = 'tests/' + os.path.basename(rel_path)
        return rel_path

    def _verify_written_plans(self, plans, snapshots, warnings, repair_iters=0, keep_failing_tests=False, pytest_args=None, generation_strategy='auto', llm_required=False, llm_temperature=0.1, llm_max_tokens=4096, partial_rollback=True, pytest_stream=True, require_runtime_proof=True):
        verification_results = []
        all_outputs = []
        all_failures = []
        all_repairs = []
        kept_files = []
        any_failed = False
        written_files = set(self._plan_rel_path(plan) for plan in plans)
        for plan in plans:
            rel_path = self._plan_rel_path(plan)
            if rel_path not in written_files:
                continue
            pytest_target = self._pytest_target_for_plan(plan, rel_path, pytest_args)
            self._print_status('RUN', f'Running pytest for {pytest_target}', 'cyan')
            returncode, output = self._run_pytest(self._pytest_targets([rel_path], pytest_target), stream=pytest_stream)
            all_outputs.append(output)
            plan_repairs = []
            remaining_repairs = max(0, int(repair_iters or 0))
            iteration = 0
            while returncode and remaining_repairs > 0:
                iteration += 1
                action = self._repair_generated_tests([plan], output, warnings, generation_strategy, llm_required, llm_temperature, llm_max_tokens)
                self._print_status('REPAIR', f'Attempt {iteration} for {rel_path} [{plan.target_id}]: {action}', 'yellow')
                returncode, output = self._run_pytest(self._pytest_targets([rel_path], pytest_target), stream=pytest_stream)
                attempt = RepairAttempt(iteration, action, returncode, output)
                plan_repairs.append(attempt)
                all_repairs.append(attempt)
                all_outputs.append(output)
                remaining_repairs -= 1
                if action == 'no-op':
                    break
            proof_status = 'skipped'
            proof_edges = []
            proof_message = ''
            if returncode == 0:
                status = 'kept'
                # M4: per-block runtime proof check (only when enabled)
                if require_runtime_proof:
                    block_edges = self._run_per_block_runtime_map(plan, rel_path)
                    proof_status, proof_edges, proof_message = self._check_runtime_proof(plan, block_edges)
                    if proof_status == 'pass':
                        self._print_status('PROOF PASS', proof_message, 'green')
                        kept_files.append(rel_path)
                        self._print_status('PASS', f'Kept generated block: {rel_path} [{plan.target_id}]', 'green')
                    else:
                        self._print_status('PROOF FAIL', proof_message + ' — rolling back block', 'red')
                        status = 'proof_rolled_back'
                        any_failed = True
                        self._remove_generated_block_for_target(plan, snapshots)
                        if self._generated_file_has_content(rel_path):
                            kept_files.append(rel_path)
                else:
                    kept_files.append(rel_path)
                    self._print_status('PASS', f'Kept generated block: {rel_path} [{plan.target_id}]', 'green')
            else:
                any_failed = True
                all_failures.extend(self._parse_pytest_failures(output))
                if keep_failing_tests:
                    status = 'kept_failing'
                    kept_files.append(rel_path)
                    self._print_status('FAIL', f'Kept failing generated block for debugging: {rel_path} [{plan.target_id}]', 'magenta')
                elif partial_rollback:
                    status = 'rolled_back'
                    self._remove_generated_block_for_target(plan, snapshots)
                    if self._generated_file_has_content(rel_path):
                        kept_files.append(rel_path)
                    self._print_status('ROLLBACK', f'Removed failing generated block: {rel_path} [{plan.target_id}]', 'red')
                else:
                    status = 'failed_pending_batch_rollback'
                    self._print_status('FAIL', f'Pending batch rollback: {rel_path}', 'red')
            verification_results.append(PlanVerificationResult(
                plan.target_id, rel_path, str(pytest_target), returncode, output, status,
                plan_repairs, proof_status, proof_edges, proof_message,
            ))
        if any_failed and not keep_failing_tests and not partial_rollback:
            self._rollback_snapshots(snapshots)
            kept_files = []
            for result in verification_results:
                if result.status in {'kept', 'failed_pending_batch_rollback'}:
                    result.status = 'batch_rolled_back'
            warnings.append('Batch rollback complete: all generated tests were restored because verification failed.')
        elif any_failed and not keep_failing_tests and partial_rollback:
            warnings.append('Block rollback complete: kept passing generated blocks and removed failing generated blocks.')
        pytest_returncode = 1 if any_failed else 0
        return verification_results, sorted(set(kept_files)), pytest_returncode, '\n'.join(all_outputs), all_failures, all_repairs, any_failed and not keep_failing_tests

    # ------------------------------------------------------------------ M4 helpers

    def _run_per_block_runtime_map(self, plan, rel_path):
        """Run per-test coverage for just the test(s) in this block. Returns list[RuntimeCoverageEdge]."""
        test_names = list(getattr(plan, 'test_names', None) or
                          self._test_function_names(getattr(plan, 'code', '') or ''))
        if not test_names:
            return []
        # Scope to first test name if single; else whole file (per-test mode will split)
        if len(test_names) == 1:
            pytest_scope = f'{rel_path}::{test_names[0]}'
        else:
            pytest_scope = rel_path
        try:
            mapper = RuntimeCoverageMapper(self.project, repo_path=self.repo_path)
            result = mapper.map_runtime_coverage(
                pytest_args=pytest_scope,
                mode='per-test',
                persist=False,  # proof-only; global persist happens later
            )
            return result.runtime_edges
        except Exception:
            return []

    def _check_runtime_proof(self, plan, runtime_edges):
        """Check if any edge in runtime_edges links a test in this plan to its target.

        Returns (proof_status, matching_edges, message).
        proof_status: 'pass' | 'fail'
        """
        test_names = set(getattr(plan, 'test_names', None) or
                         self._test_function_names(getattr(plan, 'code', '') or ''))
        target_id = plan.target_id  # e.g. FUNC:run_ingestion_pipeline

        matching = [
            e for e in runtime_edges
            if e.target_id == target_id
            and any(name in e.test_id for name in test_names)
        ]
        if matching:
            best = max(matching, key=lambda e: e.covered_fraction)
            short_test = best.test_id.split('::')[-1]
            msg = (f'edge confirmed: {short_test} → {target_id} '
                   f'({best.covered_fraction:.0%} coverage, {best.covered_line_count}/{best.function_line_count} lines)')
            return 'pass', matching, msg
        else:
            names_str = ', '.join(sorted(test_names)) if test_names else '(none)'
            msg = (f'no runtime edge to {target_id} — '
                   f'test(s) [{names_str}] did not execute the target at runtime')
            return 'fail', [], msg

    # ------------------------------------------------------------------ /M4 helpers

    def _print_status(self, label, message, color='cyan'):
        colors = {
            'cyan': '\033[96m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'red': '\033[91m',
            'magenta': '\033[95m',
        }
        reset = '\033[0m'
        bold = '\033[1m'
        color_code = colors.get(color, colors['cyan'])
        banner = f'{bold}{color_code}== SOFTGNN {label} =={reset}'
        print(f'\n{banner} {color_code}{message}{reset}', flush=True)

    def print_stage(self, stage, message):
        self._print_status(stage, message, 'cyan')

    def _rollback_plan_snapshot(self, plan, snapshots):
        rel_path = self._plan_rel_path(plan)
        abs_path = os.path.join(self.repo_path, rel_path.replace('/', os.sep))
        self._rollback_snapshots({abs_path: snapshots.get(abs_path)})

    def _pytest_target_for_plan(self, plan, rel_path, pytest_args=None):
        if pytest_args:
            return pytest_args
        names = list(getattr(plan, 'test_names', None) or self._test_function_names(getattr(plan, 'code', '') or ''))
        if len(names) == 1:
            return f'{rel_path}::{names[0]}'
        return rel_path

    def _remove_generated_block_for_target(self, plan, snapshots):
        rel_path = self._plan_rel_path(plan)
        abs_path = os.path.join(self.repo_path, rel_path.replace('/', os.sep))
        if not os.path.exists(abs_path):
            return
        content = self._read_text(abs_path)
        pattern = re.compile(
            rf'# <softgnn-generated target="{re.escape(plan.target_id)}" start>.*?# <softgnn-generated target="{re.escape(plan.target_id)}" end>\n?',
            flags=re.DOTALL,
        )
        new_content = pattern.sub('', content).rstrip() + '\n'
        original = snapshots.get(abs_path)
        if original is None and not new_content.strip():
            os.remove(abs_path)
        else:
            Path(abs_path).write_text(new_content, encoding='utf-8')

    def _generated_file_has_content(self, rel_path):
        abs_path = os.path.join(self.repo_path, rel_path.replace('/', os.sep))
        return os.path.exists(abs_path) and bool(self._read_text(abs_path).strip())

    def _pytest_targets(self, files_written, pytest_args):
        if pytest_args:
            if isinstance(pytest_args, (list, tuple)):
                return list(pytest_args)
            return str(pytest_args).split()
        return files_written

    def _parse_pytest_failures(self, output):
        failures = []
        current = None
        blocks = re.split(r'\n_{5,}\s+', output or '')
        for block in blocks:
            header_match = re.search(r'(test_[a-zA-Z0-9_]+)', block)
            if not header_match:
                continue
            error_match = re.search(r'\b(E|FAILED)\s+([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Failure)?)?:?\s*(.*)', block)
            error_type = error_match.group(2) if error_match and error_match.group(2) else 'PytestFailure'
            message = error_match.group(3).strip() if error_match else block.strip().splitlines()[-1]
            current = PytestFailure(header_match.group(1), error_type, message, block[-2000:])
            failures.append(current)
        if not failures and output:
            syntax = re.search(r'(SyntaxError|ImportError|ModuleNotFoundError|AttributeError|TypeError):\s*(.*)', output)
            if syntax:
                failures.append(PytestFailure('-', syntax.group(1), syntax.group(2), output[-2000:]))
        return failures

    def _apply_feedback_from_result(self, result):
        feedback = {}
        for item in result.verification_results or []:
            if item.status not in {'rolled_back', 'kept_failing', 'batch_rolled_back', 'failed_pending_batch_rollback'}:
                continue
            plan = next((p for p in result.plans if p.target_id == item.target_id), None)
            feedback[item.target_id] = {
                'target_id': item.target_id,
                'source_file': getattr(plan, 'source_file', ''),
                'test_file': item.test_file,
                'status': item.status,
                'repair_attempts': len(item.repair_attempts),
                'pytest_returncode': item.returncode,
                'pytest_output_tail': (item.output or '')[-4000:],
                'previous_generated_code': getattr(plan, 'code', ''),
            }
        return feedback

    def _persist_apply_run(self, result):
        from datetime import datetime, timezone
        from softgnn_advisor.config.settings import get_project_paths
        run_id = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        paths = get_project_paths(self.project)
        project_dir = Path(paths['PLANS_DIR']).parent
        apply_dir = project_dir / 'apply_runs' / run_id
        apply_dir.mkdir(parents=True, exist_ok=True)
        plan_by_target = {plan.target_id: plan for plan in result.plans}
        rows = []
        for item in result.verification_results or []:
            plan = plan_by_target.get(item.target_id)
            rows.append({
                'target_id': item.target_id,
                'source_file': getattr(plan, 'source_file', ''),
                'test_file': item.test_file,
                'pytest_target': item.pytest_target,
                'status': item.status,
                'repair_attempts': len(item.repair_attempts),
                'pytest_returncode': item.returncode,
                'pytest_output_tail': (item.output or '')[-4000:],
                'previous_generated_code': getattr(plan, 'code', ''),
                'rollback_scope': 'generated_block' if 'rolled_back' in item.status else None,
                'proof_status': getattr(item, 'proof_status', 'skipped'),
                'proof_message': getattr(item, 'proof_message', ''),
                'proof_edges': [getattr(edge, '__dict__', {}) for edge in (getattr(item, 'proof_edges', None) or [])],
            })
        payload = {
            'run_id': run_id,
            'project': self.project,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'kept': sum(1 for row in rows if row['status'] == 'kept'),
                'rolled_back': sum(1 for row in rows if 'rolled_back' in row['status']),
                'kept_failing': sum(1 for row in rows if row['status'] == 'kept_failing'),
                'proof_pass': sum(1 for row in rows if row.get('proof_status') == 'pass'),
                'proof_fail': sum(1 for row in rows if row.get('proof_status') == 'fail'),
                'proof_skipped': sum(1 for row in rows if row.get('proof_status') == 'skipped'),
            },
            'results': rows,
        }
        path = apply_dir / 'result.json'
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')
        return str(path), run_id

    def _repair_generated_tests(self, plans, pytest_output, warnings, generation_strategy='template', llm_required=False, llm_temperature=0.1, llm_max_tokens=4096):
        if generation_strategy in ('llm', 'auto') and getattr(self.llm_provider, 'available', False):
            action = self._try_llm_repair(plans, pytest_output, warnings, llm_required, llm_temperature, llm_max_tokens)
            if action != 'no-op':
                return action
        # Heuristic repair v1. Conservative by design: only generated test files are touched.
        actions = []
        if 'SyntaxError' in pytest_output:
            for plan in plans:
                original_code = plan.code
                if '\ndef\n' in plan.code or re.search(r'\ndef\s+\n\s*test_', plan.code):
                    plan.code = re.sub(r'\ndef\s+\n\s*(test_)', r'\ndef \1', plan.code)
                    actions.append('normalized malformed function definition')
                plan.code = self._repair_multiline_with_context_managers(plan.code)
                if plan.code != original_code:
                    actions.append('normalized multi-line with context managers')
        if 'GradScaler' in pytest_output and "GradScaler" in ''.join(p.code for p in plans):
            actions.append('kept CPU-safe GradScaler mock')
        if not actions:
            warnings.append('No heuristic repair matched pytest failure.')
            return 'no-op'
        self._rewrite_generated_blocks(plans)
        return '; '.join(sorted(set(actions)))

    def _repair_multiline_with_context_managers(self, code):
        lines = code.splitlines()
        repaired = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if stripped.startswith('with ') and stripped.endswith(',') and '(' not in stripped.split('with ', 1)[1].split(',', 1)[0]:
                indent = line[:len(line) - len(line.lstrip())]
                context_lines = [stripped[5:]]
                i += 1
                while i < len(lines):
                    current = lines[i]
                    current_stripped = current.strip()
                    context_lines.append(current_stripped)
                    if current_stripped.endswith(':'):
                        break
                    i += 1
                if context_lines and context_lines[-1].endswith(':'):
                    context_lines[-1] = context_lines[-1][:-1]
                    repaired.append(f'{indent}with (')
                    for idx, ctx in enumerate(context_lines):
                        suffix = '' if idx == len(context_lines) - 1 else ','
                        repaired.append(f'{indent}    {ctx}{suffix}')
                    repaired.append(f'{indent}):')
                else:
                    repaired.append(line)
                    repaired.extend(lines[i - len(context_lines) + 1:i + 1])
            else:
                repaired.append(line)
            i += 1
        return '\n'.join(repaired)

    def _try_llm_repair(self, plans, pytest_output, warnings, llm_required, llm_temperature, llm_max_tokens):
        if not plans:
            return 'no-op'
        plan = plans[0]
        context = self._collect_source_context(TestGenerationTarget(plan.target_id, getattr(plan, 'source_file', '') or '', 'repair context', 0.0))
        request = LLMRequest(
            system_prompt=self._llm_repair_system_prompt(),
            user_prompt=self._llm_repair_user_prompt(plan, pytest_output, context),
            temperature=llm_temperature,
            max_tokens=llm_max_tokens,
        )
        try:
            response = self.llm_provider.complete(request)
            fixed_code, explanation = parse_repair_response(response.text)
            plan.code = fixed_code
            plan.test_names = self._test_function_names(fixed_code)
            self._rewrite_generated_blocks([plan])
            return f'LLM repair: {explanation}'
        except Exception as exc:
            message = f'LLM repair failed; falling back to heuristic repair: {exc}'
            warnings.append(message)
            return 'no-op'

    def _llm_repair_system_prompt(self):
        return """You repair generated pytest code. Return exactly one JSON object and no markdown. Replace only the generated test block. Use the provided production source context exactly; do not invent constructor argument names or mock paths. If pytest failed due to import-time side effects, move imports inside tests and install mocks before importing the module. Keep tests deterministic, CPU-safe, and under pytest. Do not use subprocess, network, os.system, requests, urllib, socket, or destructive filesystem operations."""

    def _llm_repair_user_prompt(self, plan, pytest_output, context=None):
        context = context or {}
        return f"""
Return JSON:
{{
  "action": "replace_generated_block",
  "code": "fixed pytest code as a string",
  "explanation": "what changed"
}}

Target: {plan.target_id}
Test file: {plan.test_file}
Current generated code:
```python
{plan.code[-6000:]}
```

Pytest output:
```text
{pytest_output[-6000:]}
```

Production source context for repair:
```python
{self._focused_source_context(plan.target_id.replace('FUNC:', ''), context)[:10000]}
```

Detected import-time side effects:
```text
{chr(10).join(context.get('module_side_effects', [])) or '-'}
```

Constraints:
- Keep all code as pytest test code only.
- Preserve or improve semantic assertions.
- Do not touch production code.
- Multi-line `with` statements must use parentheses, e.g. `with (patch(...), patch(...)):`; never leave a line ending in a bare comma.
- Return JSON only.
""".strip()

    def _rewrite_generated_blocks(self, plans):
        for plan in plans:
            rel_path = plan.test_file.replace('\\', '/')
            if not rel_path.startswith('tests/'):
                rel_path = 'tests/' + os.path.basename(rel_path)
            abs_path = os.path.join(self.repo_path, rel_path.replace('/', os.sep))
            if not os.path.exists(abs_path):
                continue
            content = self._read_text(abs_path)
            pattern = re.compile(
                rf'# <softgnn-generated target="{re.escape(plan.target_id)}" start>.*?# <softgnn-generated target="{re.escape(plan.target_id)}" end>\n?',
                flags=re.DOTALL,
            )
            replacement = self._wrap_generated_block(plan)
            if pattern.search(content):
                content = pattern.sub(replacement, content)
            else:
                content = content.rstrip() + '\n\n\n' + replacement
            Path(abs_path).write_text(content, encoding='utf-8')

    def _run_pytest(self, files, stream=False):
        cmd = [sys.executable, '-m', 'pytest']
        if stream:
            cmd += ['-vv', '--tb=short']
        else:
            cmd += ['-q']
        cmd += files
        if stream:
            proc = subprocess.Popen(
                cmd,
                cwd=self.repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            output_parts = []
            assert proc.stdout is not None
            for line in proc.stdout:
                print(line, end='', flush=True)
                output_parts.append(line)
            return proc.wait(), ''.join(output_parts)
        proc = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True, encoding='utf-8', errors='replace')
        return proc.returncode, (proc.stdout or '') + (proc.stderr or '')

    def render_markdown(self, result):
        lines = [f'# Generated Test Plan — {self.project}', '', f'Mode: `{result.mode}`', '']
        if result.warnings:
            lines += ['## Warnings', ''] + [f'- {w}' for w in result.warnings] + ['']
        lines += ['## Selected Targets', '']
        if not result.targets:
            lines.append('No missing coverage function targets were selected.')
        for target in result.targets:
            lines += [
                f'### `{target.node_id}`',
                '',
                f'- Source: `{target.source_file}`',
                f'- Priority: `{target.priority:.1f}`',
                f'- Reason: {target.reason}',
                f'- Evidence: {"; ".join(target.evidence) if target.evidence else "-"}',
                '',
            ]
        lines += ['## Proposed Tests', '']
        for plan in result.plans:
            lines += [
                f'### `{plan.test_file}` for `{plan.target_id}`',
                '',
                plan.rationale,
                '',
                'Assumptions:',
                *[f'- {a}' for a in plan.assumptions],
                '',
                f'```python\n{plan.code}```',
                '',
            ]
        if result.files_written:
            lines += ['## Files Written', ''] + [f'- `{f}`' for f in result.files_written] + ['']
        if result.apply_run_path:
            lines += ['## Apply Run', '', f'- Result: `{result.apply_run_path}`', '']
        if result.verification_results:
            lines += ['## Verification Results', '', '| Test file | Target | Status | Repairs | Proof |', '|---|---|---|---|---|']
            for item in result.verification_results:
                proof_icon = {'pass': '✅ PASS', 'fail': '❌ FAIL', 'skipped': '—'}.get(
                    getattr(item, 'proof_status', 'skipped'), '—')
                proof_detail = getattr(item, 'proof_message', '')
                proof_cell = f'{proof_icon} {proof_detail}' if proof_detail else proof_icon
                lines.append(f'| `{item.test_file}` | `{item.target_id}` | `{item.status}` | `{len(item.repair_attempts)}` | {proof_cell} |')
            lines.append('')
        if result.rolled_back:
            lines += ['## Rollback', '', 'Generated edits were rolled back because verification failed.', '']
        if result.pytest_returncode is not None:
            lines += ['## Pytest Verification', '', f'Return code: `{result.pytest_returncode}`', '', '```text', result.pytest_output[-4000:], '```', '']
        if result.failures:
            lines += ['## Parsed Failures', '']
            for failure in result.failures:
                lines += [f'- `{failure.test_name}` `{failure.error_type}`: {failure.message}', '']
        if result.repair_attempts:
            lines += ['## Repair Attempts', '']
            for attempt in result.repair_attempts:
                lines += [f'- Iteration {attempt.iteration}: {attempt.action} -> return code `{attempt.pytest_returncode}`']
            lines.append('')
        if result.runtime_result is not None:
            lines += [
                '## Runtime Refresh',
                '',
                f'- Mode used: `{result.runtime_result.mode_used}`',
                f'- Discovered tests: `{len(result.runtime_result.discovered_tests)}`',
                f'- Runtime edges: `{len(result.runtime_result.runtime_edges)}`',
                f'- Persisted: `{result.runtime_result.persisted}`',
                '',
            ]
        if result.post_missing_coverage_count is not None:
            lines += [
                '## PR Scan Confirmation',
                '',
                f'- Missing coverage before: `{result.pre_missing_coverage_count}`',
                f'- Missing coverage after: `{result.post_missing_coverage_count}`',
                '',
            ]
        return '\n'.join(lines)

    def _suggest_test_file(self, source_file):
        base = os.path.splitext(os.path.basename(source_file))[0]
        return f'tests/test_{base}.py'

    def _module_path(self, source_file):
        return source_file[:-3].replace('/', '.').replace('\\', '.') if source_file.endswith('.py') else source_file.replace('/', '.')

    def _safe_name(self, value):
        return re.sub(r'[^a-zA-Z0-9_]+', '_', value).strip('_').lower()

    def _read_text(self, path):
        try:
            return Path(path).read_text(encoding='utf-8')
        except Exception:
            return ''

    def _extract_imports(self, source):
        return [line for line in source.splitlines() if line.startswith(('import ', 'from '))]

    def _slice_source(self, lines, node):
        start = max(getattr(node, 'lineno', 1) - 1, 0)
        end = getattr(node, 'end_lineno', getattr(node, 'lineno', 1))
        return '\n'.join(lines[start:end])

    def _test_function_names(self, code):
        return re.findall(r'^def (test_[a-zA-Z0-9_]+)\(', code, flags=re.MULTILINE)

    def _signature(self, node):
        args = [arg.arg for arg in node.args.args]
        if node.args.vararg:
            args.append('*' + node.args.vararg.arg)
        if node.args.kwarg:
            args.append('**' + node.args.kwarg.arg)
        return f"{node.name}({', '.join(args)})"

