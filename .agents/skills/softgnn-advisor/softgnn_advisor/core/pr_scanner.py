import ast
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from softgnn_advisor.config.settings import get_project_paths
from softgnn_advisor.core.change_provider import ChangedFile, ChangedHunk, build_change_set
from softgnn_advisor.core.impact_engine import ImpactEngine, ImpactTarget
from softgnn_advisor.infrastructure.pipelines.contract_extractor import ContractExtractor, load_contract_snapshot


@dataclass
class ChangedNode:
    key: tuple
    full_id: str
    label: str
    node_type: str
    source_file: str


@dataclass
class ImpactHotspot:
    key: tuple
    label: str
    node_type: str
    risk_score: float
    risk_level: str
    evidence: list
    sources: list
    paths: list


@dataclass
class ReviewerRecommendation:
    developer: str
    score: float
    evidence: list


@dataclass
class TestSuggestion:
    name: str
    test_type: str
    suggested_file: str
    covers: list
    reason: str


@dataclass
class ContractChange:
    function_id: str
    signature_changed: bool
    return_pattern_changed: bool
    behavior_changed: bool
    source_only_changed: bool
    summary: list


@dataclass
class RelatedTest:
    test_id: str
    target_id: str
    relation: str
    evidence: str


@dataclass
class MissingCoverage:
    target_id: str
    reason: str
    suggested_action: str


@dataclass
class PRScanResult:
    changed_files: list
    changed_nodes: list
    impact_hotspots: list
    reviewers: list
    suggested_tests: list
    warnings: list = field(default_factory=list)
    contract_changes: list = field(default_factory=list)
    related_tests: list = field(default_factory=list)
    missing_coverage: list = field(default_factory=list)
    change_source: str = 'git'


class PRScanner:
    def __init__(self, project, repo_path=None):
        self.project = project
        self.engine = ImpactEngine(project)
        self.repo_path = repo_path or self.engine.source_path or os.getcwd()
        self.repo_path = os.path.abspath(self.repo_path)
        paths = get_project_paths(project)
        self.contracts_path = str(paths.get('CONTRACTS_PATH'))
        self.contract_snapshot = load_contract_snapshot(self.contracts_path)

    def scan(self, base='main', head='HEAD', mode='hybrid', gnn_types='File,Class,Function', max_impact=30, max_reviewers=3, suggest_tests=True, change_source='auto'):
        warnings = []
        change_set = self._read_changed_files(base, head, warnings, change_source=change_source)
        changed_files = change_set.files
        changed_nodes = self._map_changed_nodes(changed_files, warnings)
        if not changed_nodes:
            return PRScanResult(changed_files, [], [], [], [], warnings, change_source=change_set.source)

        contract_changes = self._detect_contract_changes(changed_nodes, changed_files, warnings)
        impact_hotspots = self._aggregate_impact(changed_nodes, mode, gnn_types, max_impact, warnings)
        reviewers = self._recommend_reviewers(changed_files, impact_hotspots, max_reviewers)
        related_tests = self._find_related_tests(changed_nodes, impact_hotspots)
        missing_coverage = self._find_missing_coverage(changed_nodes, contract_changes, related_tests)
        tests = self._suggest_tests(changed_nodes, impact_hotspots, missing_coverage) if suggest_tests else []
        # dedup warnings while preserving order
        seen_warnings = set()
        deduped_warnings = []
        for w in warnings:
            if w not in seen_warnings:
                seen_warnings.add(w)
                deduped_warnings.append(w)
        return PRScanResult(changed_files, changed_nodes, impact_hotspots, reviewers, tests, deduped_warnings, contract_changes, related_tests, missing_coverage, change_set.source)

    def _read_changed_files(self, base, head, warnings, change_source='auto'):
        change_set = build_change_set(self.project, self.repo_path, base=base, head=head, change_source=change_source)
        warnings.extend(change_set.warnings)
        return change_set

    def _parse_file_diff(self, rel_path, diff_output):
        hunks = []
        added = 0
        deleted = 0
        current_hunk = None
        for line in diff_output.splitlines():
            header = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if header:
                start = int(header.group(3))
                length = int(header.group(4) or '1')
                end = start if length == 0 else start + length - 1
                current_hunk = ChangedHunk(start, end)
                hunks.append(current_hunk)
                continue
            if line.startswith('+++') or line.startswith('---'):
                continue
            if line.startswith('+'):
                added += 1
            elif line.startswith('-'):
                deleted += 1
        return ChangedFile(rel_path, hunks, added, deleted)

    def _map_changed_nodes(self, changed_files, warnings):
        node_by_key = {}
        transient_index = 0
        for changed_file in changed_files:
            file_id = f"FILE:{changed_file.path}"
            file_key = self.engine.key_by_full_id.get(file_id)
            if file_key:
                node_by_key[file_key] = ChangedNode(file_key, file_id, self.engine.display_node_label(file_key), 'File', changed_file.path)
            elif changed_file.path.endswith('.py') and changed_file.status != 'deleted':
                warnings.append(f"Changed Python file not found in graph; parsing incrementally: {changed_file.path}")
            elif not changed_file.path.endswith('.py'):
                warnings.append(f"Changed non-code file skipped: {changed_file.path}")
            else:
                warnings.append(f"Changed file not found in graph: {changed_file.path}")

            if not changed_file.path.endswith('.py'):
                continue
            if changed_file.status == 'deleted':
                warnings.append(f"Changed Python file was deleted; skipping test target discovery: {changed_file.path}")
                continue
            abs_path = os.path.join(self.repo_path, changed_file.path.replace('/', os.sep))
            if not os.path.exists(abs_path):
                warnings.append(f"Changed file no longer exists on disk: {changed_file.path}")
                continue
            try:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    source = f.read()
                tree = ast.parse(source)
            except Exception as e:
                warnings.append(f"Cannot parse changed Python file {changed_file.path}: {e}")
                continue
            for node_id, node_type, start, end in self._collect_symbol_ranges(tree):
                if self._overlaps_any_hunk(start, end, changed_file.hunks):
                    key = self.engine.key_by_full_id.get(node_id)
                    if key:
                        node_by_key[key] = ChangedNode(key, node_id, self.engine.display_node_label(key), node_type, changed_file.path)
                    elif changed_file.status in {'added', 'modified'}:
                        transient_index += 1
                        transient_key = ('Transient', transient_index)
                        label = node_id.replace('FUNC:', '').replace('CLASS:', '')
                        node_by_key[transient_key] = ChangedNode(transient_key, node_id, label, node_type, changed_file.path)
        return sorted(node_by_key.values(), key=lambda n: {'Function': 0, 'Class': 1, 'File': 2}.get(n.node_type, 9))[:20]

    def _collect_symbol_ranges(self, tree):
        ranges = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                end = getattr(node, 'end_lineno', node.lineno)
                ranges.append((f"CLASS:{node.name}", 'Class', node.lineno, end))
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        child_end = getattr(child, 'end_lineno', child.lineno)
                        ranges.append((f"FUNC:{node.name}.{child.name}", 'Function', child.lineno, child_end))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = getattr(node, 'end_lineno', node.lineno)
                ranges.append((f"FUNC:{node.name}", 'Function', node.lineno, end))
        return ranges

    def _overlaps_any_hunk(self, start, end, hunks):
        if not hunks:
            return True
        return any(start <= h.end_line and end >= h.start_line for h in hunks)

    def _aggregate_impact(self, changed_nodes, mode, gnn_types, max_impact, warnings):
        merged = {}
        source_counts = Counter()
        for changed_node in changed_nodes:
            if changed_node.key not in self.engine.full_id_by_key:
                warnings.append(f"Impact analysis skipped for transient node not yet persisted in graph: {changed_node.full_id}")
                continue
            target = ImpactTarget(key=changed_node.key, full_id=changed_node.full_id, node_type=changed_node.node_type)
            result = self.engine.analyze(target, mode=mode, gnn_types=gnn_types, limit=max_impact)
            if result is None:
                continue
            warnings.extend(result.warnings)
            for candidate in result.candidates:
                item = merged.setdefault(candidate.key, {
                    'label': candidate.label,
                    'node_type': candidate.node_type,
                    'score': 0.0,
                    'evidence': [],
                    'sources': [],
                    'paths': [],
                })
                item['score'] = max(item['score'], candidate.final_score)
                item['evidence'].extend(candidate.tiers)
                item['sources'].append(changed_node.full_id)
                item['paths'].extend(candidate.paths[:2])
                source_counts[candidate.key] += 1

        hotspots = []
        for key, item in merged.items():
            bonus = 0.05 * max(source_counts[key] - 1, 0)
            risk_score = min(1.0, item['score'] + bonus)
            evidence = list(dict.fromkeys(item['evidence']))
            risk_level = self._risk_level(risk_score, evidence)
            hotspots.append(ImpactHotspot(
                key=key,
                label=item['label'],
                node_type=item['node_type'],
                risk_score=risk_score,
                risk_level=risk_level,
                evidence=evidence,
                sources=list(dict.fromkeys(item['sources'])),
                paths=list(dict.fromkeys(item['paths']))[:3],
            ))
        hotspots.sort(key=lambda h: h.risk_score, reverse=True)
        return hotspots[:max_impact]

    def _risk_level(self, score, evidence):
        exploratory = evidence and all(e == 'GNN-suggested' for e in evidence)
        if score >= 0.75:
            level = 'High'
        elif score >= 0.45:
            level = 'Medium'
        else:
            level = 'Low'
        return f"{level} / Exploratory" if exploratory else level

    def _recommend_reviewers(self, changed_files, hotspots, max_reviewers):
        changed_file_keys = {self.engine.key_by_full_id.get(f"FILE:{cf.path}") for cf in changed_files}
        changed_file_keys.discard(None)
        impacted_file_keys = set()
        for hotspot in hotspots:
            if hotspot.key[0] == 'File':
                impacted_file_keys.add(hotspot.key)
            else:
                for rel, parent in self.engine.in_edges.get(hotspot.key, []):
                    if rel == 'defines' and parent[0] == 'File':
                        impacted_file_keys.add(parent)
                    elif rel == 'defines' and parent[0] == 'Class':
                        for rel2, file_key in self.engine.in_edges.get(parent, []):
                            if rel2 == 'defines' and file_key[0] == 'File':
                                impacted_file_keys.add(file_key)

        broad = Counter()
        changed = Counter()
        impacted = Counter()
        for commit_key, edges in self.engine.out_edges.items():
            if commit_key[0] != 'Commit':
                continue
            developers = [dev for rel, dev in self.engine.in_edges.get(commit_key, []) if rel == 'authored_by' and dev[0] == 'Developer']
            modified_files = [file_key for rel, file_key in edges if rel == 'modifies' and file_key[0] == 'File']
            for dev in developers:
                broad[dev] += len(modified_files)
                changed[dev] += sum(1 for f in modified_files if f in changed_file_keys)
                impacted[dev] += sum(1 for f in modified_files if f in impacted_file_keys)

        def norm(counter, key):
            max_value = max(counter.values()) if counter else 0
            return (counter[key] / max_value) if max_value else 0.0

        recommendations = []
        for dev in set(broad) | set(changed) | set(impacted):
            score = 0.45 * norm(changed, dev) + 0.35 * norm(impacted, dev) + 0.05 * norm(broad, dev)
            if score <= 0:
                continue
            developer = self.engine.full_id_by_key.get(dev, str(dev)).replace('DEV:', '')
            evidence = []
            if changed[dev]:
                evidence.append(f"touched changed files {changed[dev]} times")
            if impacted[dev]:
                evidence.append(f"touched impacted files {impacted[dev]} times")
            if broad[dev]:
                evidence.append(f"repo activity {broad[dev]} file touches")
            recommendations.append(ReviewerRecommendation(developer, min(1.0, score), evidence))
        recommendations.sort(key=lambda r: r.score, reverse=True)
        return recommendations[:max_reviewers]

    def _detect_contract_changes(self, changed_nodes, changed_files, warnings):
        extractor = ContractExtractor(self.repo_path)
        contracts_by_file = {}
        for changed_file in changed_files:
            if not changed_file.path.endswith('.py'):
                continue
            abs_path = os.path.join(self.repo_path, changed_file.path.replace('/', os.sep))
            if os.path.exists(abs_path):
                contracts_by_file.update(extractor.extract_file(abs_path, changed_file.path))
        changes = []
        for node in changed_nodes:
            if node.node_type != 'Function':
                continue
            new_contract = contracts_by_file.get(node.full_id)
            old_contract = self.contract_snapshot.get(node.full_id)
            if not new_contract or not old_contract:
                continue
            diff = extractor.diff_contracts(old_contract, new_contract)
            if not diff:
                continue
            if any(diff[k] for k in ('signature_changed', 'return_pattern_changed', 'behavior_changed', 'source_only_changed')):
                summary = []
                if diff['signature_changed']:
                    summary.append('signature changed')
                if diff['return_pattern_changed']:
                    summary.append('return pattern changed')
                if diff['behavior_changed']:
                    summary.append('behavior contract changed')
                if diff['source_only_changed']:
                    summary.append('implementation changed without detected contract-shape change')
                changes.append(ContractChange(
                    function_id=node.full_id,
                    signature_changed=diff['signature_changed'],
                    return_pattern_changed=diff['return_pattern_changed'],
                    behavior_changed=diff['behavior_changed'],
                    source_only_changed=diff['source_only_changed'],
                    summary=summary,
                ))
        return changes

    def _find_related_tests(self, changed_nodes, hotspots):
        target_ids = {node.full_id for node in changed_nodes}
        target_ids.update(h.label if h.node_type != 'File' else f"FILE:{h.label}" for h in hotspots[:10])
        relation_priority = {
            'executes_runtime': 0,
            'validates_static': 1,
            'partially_validates_static': 2,
            'executes_static': 3,
        }
        related = []
        seen = set()
        for src, edges in self.engine.out_edges.items():
            if src[0] != 'TestFunction':
                continue
            test_id = self.engine.full_id_by_key.get(src, str(src))
            for rel, dst in edges:
                dst_id = self.engine.full_id_by_key.get(dst, str(dst))
                if rel in relation_priority:
                    target_match = dst_id in target_ids or any(dst_id.endswith(t.replace('FUNC:', '').replace('CLASS:', '')) for t in target_ids)
                    if target_match:
                        key = (test_id, rel, dst_id)
                        if key not in seen:
                            evidence = 'runtime coverage' if rel == 'executes_runtime' else 'graph edge'
                            related.append(RelatedTest(test_id, dst_id, rel, evidence))
                            seen.add(key)
        related.sort(key=lambda r: relation_priority.get(r.relation, 99))
        return related[:20]

    def _find_missing_coverage(self, changed_nodes, contract_changes, related_tests):
        missing = []
        for change in contract_changes:
            if change.signature_changed or change.return_pattern_changed:
                validating = [r for r in related_tests if r.target_id.startswith('CONTRACT:') and change.function_id.replace('FUNC:', '') in r.target_id and 'validates' in r.relation]
                if not validating:
                    missing.append(MissingCoverage(
                        target_id=change.function_id,
                        reason='changed signature/return contract has no validating static test edge',
                        suggested_action='update an existing related test or add a contract-specific test',
                    ))
        for node in changed_nodes:
            if node.node_type != 'Function':
                continue
            node_related = [r for r in related_tests if r.target_id == node.full_id]
            has_runtime = any(r.relation == 'executes_runtime' for r in node_related)
            has_static = any(r.relation in ('executes_static', 'validates_static', 'partially_validates_static') for r in node_related)
            if has_runtime:
                continue
            if has_static:
                missing.append(MissingCoverage(
                    target_id=node.full_id,
                    reason='static-only test coverage found; runtime coverage unconfirmed',
                    suggested_action='run test-map or inspect runtime coverage evidence',
                ))
            else:
                missing.append(MissingCoverage(
                    target_id=node.full_id,
                    reason='no runtime or static test execution edge found for changed function',
                    suggested_action='add focused unit coverage or improve runtime/static mapping',
                ))
        return missing[:20]

    def _suggest_tests(self, changed_nodes, hotspots, missing_coverage=None):
        missing_coverage = missing_coverage or []
        suggestions = []
        seen_names = set()
        for gap in missing_coverage[:5]:
            test_name = f"test_{self._safe_name(gap.target_id)}_contract_coverage"
            if test_name in seen_names:
                continue
            suggestions.append(TestSuggestion(
                test_name,
                'contract',
                self._suggest_test_file(gap.target_id),
                [gap.target_id],
                gap.reason,
            ))
            seen_names.add(test_name)
        for node in changed_nodes[:8]:
            node_slug = self._safe_name(node.full_id.replace('FUNC:', '').replace('CLASS:', '').replace('FILE:', ''))
            if node.node_type == 'Function':
                test_name = f"test_{node_slug}_changed_behavior"
                suggested_file = self._suggest_test_file(node.source_file)
                suggestions.append(TestSuggestion(test_name, 'unit', suggested_file, [node.full_id], 'Changed function should have focused unit coverage.'))
                seen_names.add(test_name)
            elif node.node_type == 'Class':
                test_name = f"test_{node_slug}_integration"
                suggested_file = self._suggest_test_file(node.source_file)
                suggestions.append(TestSuggestion(test_name, 'integration', suggested_file, [node.full_id], 'Changed class should be covered through construction or primary behavior.'))
                seen_names.add(test_name)

        for hotspot in hotspots[:5]:
            if not hotspot.sources:
                continue
            source = hotspot.sources[0].replace('FUNC:', '').replace('CLASS:', '').replace('FILE:', '')
            test_name = f"test_{self._safe_name(source)}_to_{self._safe_name(hotspot.label)}_impact"
            if test_name in seen_names:
                continue
            test_type = 'regression' if 'Historical' in hotspot.evidence or 'GNN-suggested' in hotspot.evidence else 'integration'
            suggested_file = self._suggest_test_file(hotspot.label if hotspot.node_type == 'File' else hotspot.sources[0])
            suggestions.append(TestSuggestion(test_name, test_type, suggested_file, [hotspot.label], f"Covers impacted hotspot with {', '.join(hotspot.evidence[:2])} evidence."))
            seen_names.add(test_name)
        return suggestions[:10]

    def _suggest_test_file(self, source_file):
        rel = source_file.replace('FILE:', '').replace('FUNC:', '').replace('CLASS:', '').replace('\\', '/')
        if rel.endswith('.py'):
            basename = os.path.basename(rel)
        else:
            basename = f"test_{self._safe_name(rel)}.py"
        if not basename.startswith('test_'):
            basename = f"test_{basename}"
        return f"tests/{basename}"

    def _safe_name(self, value):
        value = value.replace('(', '').replace(')', '').replace('.', '_').replace('/', '_').replace(' ', '_')
        value = re.sub(r'[^0-9a-zA-Z_]+', '_', value).strip('_').lower()
        return value or 'target'

