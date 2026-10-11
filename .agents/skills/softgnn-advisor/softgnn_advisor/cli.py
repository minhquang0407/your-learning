import click
import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
import time

# Force UTF-8 encoding for Windows to prevent CP1252 crashes on Vietnamese/emoji text
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


console = Console()


@click.group()
def cli():
    """SoftGNN - AI-Powered Codebase Dependency & Impact Advisor"""
    pass


@cli.command()
@click.option('--project', required=True, help='Project name for isolated SoftGNN data')
@click.option('--path', default='.', help='Path to the repository to scan')
def etl(project, path):
    """Scan source code and Git history to build the knowledge graph."""
    console.rule(f"[bold blue]SoftGNN ETL Pipeline - Project: {project}")
    console.print(f"Scanning target: [yellow]{os.path.abspath(path)}[/yellow]")

    from softgnn_advisor.scripts.etl_run import run_etl_pipeline
    try:
        run_etl_pipeline(path, project)
        console.print("[bold green][SUCCESS] ETL Pipeline completed successfully![/bold green]")
        console.print(f"Graph data saved to [cyan]data_output/{project}/[/cyan]")
    except Exception as e:
        console.print(f"[bold red][ERROR] ETL Error: {e}[/bold red]")
        raise


@cli.command()
@click.option('--project', required=True, help='Project name to train')
def train(project):
    """Train the HGT (Heterogeneous Graph Transformer) AI core."""
    console.rule(f"[bold magenta]Training Core AI (HGT) - Project: {project}")

    from softgnn_advisor.scripts.train_model import run_optimization
    try:
        run_optimization(project)
        console.print("\n[bold green][SUCCESS] Training completed![/bold green]")
    except Exception as e:
        console.print(f"\n[bold red][ERROR] Training Error: {e}[/bold red]")
        raise


@cli.command()
@click.option('--project', required=True, help='Project name')
@click.option('--path', default='.', help='Path to the repository to scan and optionally train')
@click.option('--skip-train/--with-train', default=False, show_default=True, help='Build graph/snapshot without training the HGT model')
def prepare(project, path, skip_train):
    """Run the onboarding pipeline: ETL -> optional Train."""
    console.rule(f"[bold cyan]SoftGNN Prepare Pipeline - Project: {project}")
    console.print(f"Step 1/2: ETL for [yellow]{os.path.abspath(path)}[/yellow]")

    from softgnn_advisor.scripts.etl_run import run_etl_pipeline
    from softgnn_advisor.scripts.train_model import run_optimization
    from softgnn_advisor.core.change_provider import build_filesystem_snapshot, save_filesystem_snapshot, snapshot_path_for_project

    try:
        run_etl_pipeline(path, project)
        snapshot = build_filesystem_snapshot(path)
        save_filesystem_snapshot(snapshot_path_for_project(project), snapshot)
        console.print("[bold green][SUCCESS] ETL completed and filesystem snapshot saved.[/bold green]")

        if skip_train:
            console.print("[yellow]Skipping HGT training because --skip-train was set.[/yellow]")
            console.print(f"You can now run: [cyan]python softgnn.py pr-scan --project {project} --repo-path {os.path.abspath(path)} --change-source auto[/cyan]")
            return

        console.print("\nStep 2/2: Training HGT model")
        run_optimization(project)
        console.print("\n[bold green][SUCCESS] Prepare completed: ETL + Train done.[/bold green]")
        console.print(f"You can now run: [cyan]python softgnn.py doctor --project {project}[/cyan]")
    except Exception as e:
        console.print(f"[bold red][ERROR] Prepare failed: {e}[/bold red]")
        raise

@cli.command('generate-tests')
@click.option('--project', required=True, help='Project name')
@click.option('--base', default='main', show_default=True, help='Base git ref')
@click.option('--head', default='HEAD', show_default=True, help='Head git ref')
@click.option('--repo-path', default=None, help='Optional repository path override')
@click.option('--mode', type=click.Choice(['plan', 'patch']), default='plan', show_default=True, help='Generate a plan or write test files')
@click.option('--max-targets', default=3, show_default=True, help='Maximum missing-coverage targets')
@click.option('--target-id', default=None, help='Explicit function id, e.g. FUNC:HGTLinkPrediction.__init__')
@click.option('--source-file', default=None, help='Source file for explicit target id, e.g. scripts/train_model.py')
@click.option('--verify/--no-verify', default=True, show_default=True, help='Run pytest for generated files in patch mode')
@click.option('--repair-iters', default=0, show_default=True, help='Bounded heuristic repair loops after pytest failure')
@click.option('--refresh-runtime/--no-refresh-runtime', default=None, help='Run test-map automatically after pytest passes; defaults to on in patch+verify mode')
@click.option('--runtime-mode', type=click.Choice(['auto', 'dynamic-context', 'per-test']), default='auto', show_default=True, help='Runtime coverage mode for automatic refresh')
@click.option('--confirm-pr-scan/--no-confirm-pr-scan', default=True, show_default=True, help='Run pr-scan confirmation after runtime refresh')
@click.option('--keep-failing-tests/--rollback-failing-tests', default=False, show_default=True, help='Keep generated tests when verification fails instead of rolling back')
@click.option('--pytest-args', default=None, help='Override pytest args for verification and runtime refresh')
@click.option('--generation-strategy', type=click.Choice(['template', 'llm', 'auto']), default='auto', show_default=True, help='Use templates, LLM, or LLM with template fallback')
@click.option('--llm-provider', default=None, help='LLM provider override, e.g. openai-compatible')
@click.option('--llm-model', default=None, help='LLM model override')
@click.option('--llm-base-url', default=None, help='LLM base URL override')
@click.option('--llm-api-key-env', default=None, help='Name of env var containing the LLM API key')
@click.option('--llm-required/--llm-fallback', default=False, show_default=True, help='Fail if LLM is unavailable instead of falling back to templates')
@click.option('--llm-temperature', default=0.1, show_default=True, help='LLM temperature')
@click.option('--llm-max-tokens', default=4096, show_default=True, help='LLM max output tokens')
@click.option('--change-source', type=click.Choice(['auto', 'git', 'filesystem', 'full-scan']), default='auto', show_default=True, help='Detect changes from git, filesystem snapshot, or full scan')
def generate_tests(project, base, head, repo_path, mode, max_targets, target_id, source_file, verify, repair_iters, refresh_runtime, runtime_mode, confirm_pr_scan, keep_failing_tests, pytest_args, generation_strategy, llm_provider, llm_model, llm_base_url, llm_api_key_env, llm_required, llm_temperature, llm_max_tokens, change_source):
    """Generate impact-aware pytest plans or conservative test patches."""
    from softgnn_advisor.core.test_generation_agent import TestGenerationAgent

    console.rule(f"[bold cyan]SoftGNN Test Generation - Project: {project}")
    console.print(f"Range: [cyan]{base}...{head}[/cyan]")
    console.print(f"Mode: [yellow]{mode}[/yellow]")
    try:
        import os
        llm_api_key = os.getenv(llm_api_key_env) if llm_api_key_env else None
        agent = TestGenerationAgent(
            project,
            repo_path=repo_path,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_base_url=llm_base_url,
            llm_api_key=llm_api_key,
        )
        result = agent.generate(
            base=base,
            head=head,
            mode=mode,
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
        )
    except Exception as e:
        console.print(f"[bold red][ERROR] Test generation failed: {e}[/bold red]")
        raise

    markdown = agent.render_markdown(result)
    console.print(markdown)
    if result.files_written:
        console.print(f"[bold green]Wrote {len(result.files_written)} test file(s).[/bold green]")
    elif mode == 'plan':
        console.print("[bold green]Generated test plan without modifying files.[/bold green]")


@cli.command('test-map')
@click.option('--project', required=True, help='Project name')
@click.option('--repo-path', default=None, help='Optional repository path override')
@click.option('--pytest-args', default='tests', show_default=True, help='Arguments passed to pytest')
@click.option('--mode', type=click.Choice(['auto', 'dynamic-context', 'per-test']), default='auto', show_default=True, help='Runtime coverage mode')
@click.option('--persist/--no-persist', default=True, show_default=True, help='Persist runtime edges to graph and PyG data')
@click.option('--max-tests', default=None, type=int, help='Optional safety limit for discovered tests')
def test_map(project, repo_path, pytest_args, mode, persist, max_tests):
    """Map pytest runtime coverage to TestFunction -> executes_runtime -> Function edges."""
    from softgnn_advisor.infrastructure.pipelines.runtime_coverage_mapper import RuntimeCoverageMapper

    console.rule(f"[bold cyan]SoftGNN Runtime Test Mapping - Project: {project}")
    console.print(f"Mode: [cyan]{mode}[/cyan]")
    console.print(f"Pytest args: [yellow]{pytest_args}[/yellow]")
    try:
        mapper = RuntimeCoverageMapper(project, repo_path=repo_path)
        result = mapper.map_runtime_coverage(pytest_args=pytest_args, mode=mode, persist=persist, max_tests=max_tests)
    except Exception as e:
        console.print(f"[bold red][ERROR] Runtime coverage mapping failed: {e}[/bold red]")
        raise

    for warning in result.warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    summary = Table(title="Runtime Test Mapping Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="green")
    summary.add_row("Mode used", result.mode_used)
    summary.add_row("Discovered tests", str(len(result.discovered_tests)))
    summary.add_row("Mapped tests", str(result.passed_tests))
    summary.add_row("Unmapped/failed tests", str(result.failed_tests))
    summary.add_row("Runtime edges", str(len(result.runtime_edges)))
    summary.add_row("Persisted", str(result.persisted))
    console.print(summary)

    if result.runtime_edges:
        edge_table = Table(title="Runtime Coverage Edges")
        edge_table.add_column("#", justify="right", style="cyan")
        edge_table.add_column("Test", style="magenta")
        edge_table.add_column("Function", style="yellow")
        edge_table.add_column("File", style="white")
        edge_table.add_column("Covered", justify="right", style="green")
        for idx, edge in enumerate(result.runtime_edges[:30], start=1):
            edge_table.add_row(
                str(idx),
                edge.test_id,
                edge.target_id,
                edge.source_file,
                f"{edge.covered_line_count}/{edge.function_line_count} ({edge.covered_fraction:.1%})",
            )
        console.print(edge_table)

    console.print("[bold green]Runtime test mapping complete.[/bold green]")


@cli.command('pr-scan')
@click.option('--project', required=True, help='Project name')
@click.option('--base', default='main', show_default=True, help='Base git ref')
@click.option('--head', default='HEAD', show_default=True, help='Head git ref')
@click.option('--repo-path', default=None, help='Optional repository path override')
@click.option('--change-source', type=click.Choice(['auto', 'git', 'filesystem', 'full-scan']), default='auto', show_default=True, help='Detect changes from git, filesystem snapshot, or full scan')
@click.option('--mode', type=click.Choice(['deterministic', 'hybrid', 'gnn']), default='hybrid', show_default=True, help='Impact scoring mode')
@click.option('--gnn-types', default='File,Class,Function', show_default=True, help='Comma-separated node types for GNN impact candidates')
@click.option('--max-impact', default=30, show_default=True, help='Maximum impact hotspots to show')
@click.option('--max-reviewers', default=3, show_default=True, help='Maximum reviewers to recommend')
@click.option('--suggest-tests/--no-suggest-tests', default=True, show_default=True, help='Suggest tests for changed and impacted nodes')
@click.option('--report/--no-report', default=False, show_default=True, help='Write a static HTML PR intelligence report')
@click.option('--open-report', is_flag=True, help='Open the generated HTML report in a browser')
@click.option('--smart/--no-smart', default=True, show_default=True, help='Use safe read-only fallback when the default diff is empty')
@click.option('--fallback-full-scan', is_flag=True, help='If smart scan finds no git/filesystem changes, scan the full project')
def pr_scan(project, base, head, repo_path, change_source, mode, gnn_types, max_impact, max_reviewers, suggest_tests, report, open_report, smart, fallback_full_scan):
    """Scan a local PR/diff and recommend impact, reviewers, and tests."""
    from softgnn_advisor.core.pr_scanner import PRScanner

    console.print(Panel(
        f"Running PR Scan\n"
        f"Project: [yellow]{project}[/yellow]\n"
        f"Range: [cyan]{base}...{head}[/cyan]\n"
        f"Change source: [cyan]{change_source}[/cyan]\n"
        f"Mode: [cyan]{mode}[/cyan]"
    ))
    try:
        scanner = PRScanner(project, repo_path=repo_path)
        effective_repo = scanner.repo_path
        result, effective_base, effective_head, effective_source = _run_read_only_scan(
            scanner,
            project,
            effective_repo,
            base,
            head,
            mode=mode,
            gnn_types=gnn_types,
            max_impact=max_impact,
            max_reviewers=max_reviewers,
            suggest_tests=suggest_tests,
            change_source=change_source,
            smart=smart,
            fallback_full_scan=fallback_full_scan,
        )
    except FileNotFoundError as e:
        console.print(f"[bold red][ERROR] {e}[/bold red]")
        return

    for warning in result.warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    summary = Table(title="PR Scan Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="green")
    summary.add_row("Change source", result.change_source)
    summary.add_row("Changed files", str(len(result.changed_files)))
    summary.add_row("Changed graph nodes", str(len(result.changed_nodes)))
    summary.add_row("Impact hotspots", str(len(result.impact_hotspots)))
    summary.add_row("Contract changes", str(len(result.contract_changes)))
    summary.add_row("Related tests", str(len(result.related_tests)))
    summary.add_row("Missing coverage", str(len(result.missing_coverage)))
    summary.add_row("Reviewer recommendations", str(len(result.reviewers)))
    summary.add_row("Test suggestions", str(len(result.suggested_tests)))
    console.print(summary)

    if result.changed_files:
        files_table = Table(title="Changed Files")
        files_table.add_column("#", justify="right", style="cyan")
        files_table.add_column("File", style="magenta")
        files_table.add_column("Hunks", justify="right", style="yellow")
        files_table.add_column("Status", style="blue")
        files_table.add_column("Source", style="cyan")
        files_table.add_column("+/-", style="green")
        for idx, changed_file in enumerate(result.changed_files[:20], start=1):
            files_table.add_row(str(idx), changed_file.path, str(len(changed_file.hunks)), getattr(changed_file, 'status', 'modified'), getattr(changed_file, 'source', result.change_source), f"+{changed_file.added_lines}/-{changed_file.deleted_lines}")
        console.print(files_table)

    if result.changed_nodes:
        nodes_table = Table(title="Changed Graph Nodes")
        nodes_table.add_column("#", justify="right", style="cyan")
        nodes_table.add_column("Node", style="magenta")
        nodes_table.add_column("Type", style="blue")
        nodes_table.add_column("Source File", style="white")
        for idx, node in enumerate(result.changed_nodes[:20], start=1):
            nodes_table.add_row(str(idx), node.label, node.node_type, node.source_file)
        console.print(nodes_table)

    if result.impact_hotspots:
        impact_table = Table(title="Impact Hotspots")
        impact_table.add_column("Rank", justify="right", style="cyan")
        impact_table.add_column("Node", style="magenta")
        impact_table.add_column("Type", style="blue")
        impact_table.add_column("Risk", justify="right", style="green")
        impact_table.add_column("Level", style="yellow")
        impact_table.add_column("Evidence", style="cyan")
        impact_table.add_column("Source", style="white")
        for idx, hotspot in enumerate(result.impact_hotspots[:max_impact], start=1):
            impact_table.add_row(
                str(idx), hotspot.label, hotspot.node_type,
                f"{hotspot.risk_score * 100:.1f}%",
                hotspot.risk_level,
                ', '.join(hotspot.evidence[:3]),
                hotspot.sources[0] if hotspot.sources else '-',
            )
        console.print(impact_table)

    if result.reviewers:
        reviewer_table = Table(title="Recommended Reviewers")
        reviewer_table.add_column("Rank", justify="right", style="cyan")
        reviewer_table.add_column("Reviewer", style="magenta")
        reviewer_table.add_column("Score", justify="right", style="green")
        reviewer_table.add_column("Evidence", style="white")
        for idx, reviewer in enumerate(result.reviewers, start=1):
            reviewer_table.add_row(str(idx), reviewer.developer, f"{reviewer.score * 100:.1f}%", '; '.join(reviewer.evidence[:3]))
        console.print(reviewer_table)

    if result.contract_changes:
        contract_table = Table(title="Contract Changes")
        contract_table.add_column("Function", style="magenta")
        contract_table.add_column("Signature", style="cyan")
        contract_table.add_column("Return", style="cyan")
        contract_table.add_column("Behavior", style="yellow")
        contract_table.add_column("Summary", style="white")
        for change in result.contract_changes[:20]:
            contract_table.add_row(
                change.function_id,
                "yes" if change.signature_changed else "no",
                "yes" if change.return_pattern_changed else "no",
                "yes" if change.behavior_changed else ("source-only" if change.source_only_changed else "no"),
                '; '.join(change.summary),
            )
        console.print(contract_table)

    if result.related_tests:
        related_table = Table(title="Existing Related Tests")
        related_table.add_column("Test", style="magenta")
        related_table.add_column("Relation", style="cyan")
        related_table.add_column("Target", style="yellow")
        related_table.add_column("Evidence", style="white")
        for related in result.related_tests[:20]:
            related_table.add_row(related.test_id, related.relation, related.target_id, related.evidence)
        console.print(related_table)

    if result.missing_coverage:
        missing_table = Table(title="Missing Test / Contract Coverage")
        missing_table.add_column("Target", style="magenta")
        missing_table.add_column("Reason", style="yellow")
        missing_table.add_column("Suggested Action", style="white")
        for gap in result.missing_coverage[:20]:
            missing_table.add_row(gap.target_id, gap.reason, gap.suggested_action)
        console.print(missing_table)

    if result.suggested_tests:
        tests_table = Table(title="Suggested Tests")
        tests_table.add_column("#", justify="right", style="cyan")
        tests_table.add_column("Test", style="magenta")
        tests_table.add_column("Type", style="blue")
        tests_table.add_column("Suggested File", style="yellow")
        tests_table.add_column("Reason", style="white")
        for idx, test in enumerate(result.suggested_tests, start=1):
            tests_table.add_row(str(idx), test.name, test.test_type, test.suggested_file, test.reason)
        console.print(tests_table)

    if report:
        from softgnn_advisor.core.report_renderer import build_generate_report_payload
        payload = build_generate_report_payload(
            project=project,
            scan_result=result,
            repo_path=repo_path,
        )
        _save_and_show_report(project, payload, open_report=open_report)

    console.print("\n[bold green]PR Scan Complete.[/bold green] Results are evidence-grounded; GNN-only items are exploratory suggestions.")


@cli.command()
@click.option('--project', required=True, help='Project name')
@click.option('--mode', type=click.Choice(['deterministic', 'hybrid', 'gnn']), default='deterministic', show_default=True, help='Impact scoring mode')
@click.option('--gnn-types', default='File,Class,Function', show_default=True, help='Comma-separated node types for GNN impact candidates')
@click.argument('function_name')
def impact(project, mode, gnn_types, function_name):
    """Predict functions/files at risk when changing a target."""
    from softgnn_advisor.core.impact_engine import ImpactEngine

    console.print(Panel(
        f"Running Change Impact Analysis for: [bold cyan]{function_name}[/bold cyan]\n"
        f"Project: [yellow]{project}[/yellow]\n"
        f"Mode: [cyan]{mode}[/cyan]"
    ))

    try:
        engine = ImpactEngine(project)
    except FileNotFoundError as e:
        console.print(f"[bold red][ERROR] {e}[/bold red]")
        return

    def status_callback(fn):
        with console.status("Computing GNN impact proximity...", spinner="dots"):
            return fn()

    result = engine.analyze(function_name, mode=mode, gnn_types=gnn_types, limit=10, status_callback=status_callback)
    if result is None:
        console.print(f"[bold red][ERROR] Cannot find any File/Function/Class matching '{function_name}'[/bold red]")
        return

    for warning in result.warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    console.print(f"Target identified: [bold green]{result.target.full_id}[/bold green] (Type: {result.target.node_type})")

    if result.internal_members:
        internal_table = Table(title="Internal Members / Direct Definitions")
        internal_table.add_column("#", justify="right", style="cyan", no_wrap=True)
        internal_table.add_column("Node", style="magenta")
        internal_table.add_column("Type", style="blue")
        internal_table.add_column("Relation", style="yellow")
        internal_table.add_column("Path", style="white")
        for idx, (key, relation, path) in enumerate(result.internal_members[:12], start=1):
            internal_table.add_row(str(idx), engine.display_node_label(key), key[0], relation, path)
        console.print(internal_table)

    if not result.candidates:
        console.print("[yellow]No downstream impact candidates found. If this graph was built before symbol-use edges existed, rerun ETL/prepare.[/yellow]")
        return

    table = Table(title="Downstream Dependents / Impact Candidates")
    table.add_column("Rank", justify="right", style="cyan", no_wrap=True)
    table.add_column("Node", style="magenta")
    table.add_column("Type", style="blue")
    if result.mode in {'hybrid', 'gnn'}:
        table.add_column("Final", justify="right", style="green")
        table.add_column("Rule", justify="right", style="yellow")
        table.add_column("GNN", justify="right", style="blue")
    else:
        table.add_column("Impact", justify="right", style="green")
    table.add_column("Evidence", style="cyan")
    table.add_column("Relation", style="yellow")
    table.add_column("Path", style="white")

    for idx, candidate in enumerate(result.candidates, start=1):
        evidence = ', '.join(candidate.tiers[:2])
        relation = ', '.join(candidate.relations)
        path = candidate.paths[0] if candidate.paths else '-'
        if result.mode in {'hybrid', 'gnn'}:
            table.add_row(
                str(idx), candidate.label, candidate.node_type,
                f"{candidate.final_score * 100:.1f}%",
                f"{candidate.rule_score * 100:.1f}%",
                f"{candidate.gnn_score * 100:.1f}%",
                evidence, relation, path,
            )
        else:
            table.add_row(str(idx), candidate.label, candidate.node_type, f"{candidate.final_score * 100:.1f}%", evidence, relation, path)

    console.print(table)
    console.print("\n[bold]Evidence legend:[/bold] Direct = node directly depends on target; Context = file/class containing a direct dependent; Historical = Git co-change fallback; GNN-suggested = embedding-proximity suggestion without a deterministic path.")
    if result.mode == 'hybrid':
        console.print("[bold]Hybrid scoring:[/bold] with rule evidence: Final = 85% Rule + 15% GNN; GNN-only: Final = 20% GNN.")
    elif result.mode == 'gnn':
        console.print(f"[bold]GNN scoring:[/bold] Final = GNN embedding proximity rank percentile over candidate types: {', '.join(sorted(result.gnn_type_filter))}. Use this for exploratory suggestions, not hard dependency evidence.")
    if result.direct_count == 0:
        console.print("[yellow]No direct code dependency found; results are historical/GNN suggestions only.[/yellow]")
    console.print("\n[bold green]Analysis Complete.[/bold green] Internal definitions are separated from downstream impact evidence.")


@cli.command()
@click.option('--project', required=True, help='Project name')
@click.argument('bug_description')
def triage(project, bug_description):
    """Recommend the best-suited engineers for a new bug."""
    from softgnn_advisor.core.triage_engine import TriageEngine

    console.print(Panel(
        f"[SEARCH] Bug Triage Analysis\n"
        f"Project: [yellow]{project}[/yellow]\n"
        f"Bug: [italic]{bug_description}[/italic]"
    ))

    engine = TriageEngine(project)
    result = engine.triage(bug_description)

    if result.get("status") == "error":
        console.print(f"[bold red][ERROR] {result.get('message')}[/bold red]")
        return
    elif result.get("status") == "warning":
        console.print(f"[yellow]{result.get('message')}[/yellow]")
        return

    top_related_files = result.get("related_files", [])
    if top_related_files:
        related_table = Table(title="Bug-related Files (Hybrid Relevance)")
        related_table.add_column("Rank", justify="right", style="cyan")
        related_table.add_column("File", style="magenta")
        related_table.add_column("Relevance", justify="right", style="green")
        related_table.add_column("Semantic", justify="right", style="blue")
        related_table.add_column("Lexical", justify="right", style="yellow")
        for f_info in top_related_files:
            related_table.add_row(
                str(f_info["rank"]),
                f_info["file"],
                f"{f_info['relevance'] * 100:.1f}%",
                f"{f_info['semantic_score'] * 100:.1f}%",
                f"{f_info['lexical_score'] * 100:.1f}%",
            )
        console.print(related_table)

    top_engineers = result.get("top_engineers", [])
    table = Table(title="Top Recommended Developers (Hybrid Scoring)")
    table.add_column("Rank", justify="right", style="cyan", no_wrap=True)
    table.add_column("Developer", style="magenta")
    table.add_column("Final", justify="right", style="green")
    table.add_column("GNN", justify="right", style="blue")
    table.add_column("Git", justify="right", style="yellow")
    table.add_column("Evidence", style="white")

    for eng in top_engineers:
        table.add_row(
            str(eng["rank"]),
            eng["developer"],
            f"{eng['final_score'] * 100:.1f}%",
            f"{eng['gnn_score'] * 100:.1f}%",
            f"{eng['git_score'] * 100:.1f}%",
            eng["evidence"],
        )

    console.print(table)
    console.print("\n[bold green]Triage Complete.[/bold green]")


@cli.command()
@click.option('--project', required=True, help='Project name to inspect')
def inspect(project):
    """Inspect the quality of a project's knowledge graph."""
    try:
        import torch
        import torch_geometric.transforms as T
    except ImportError as exc:
        raise click.ClickException(
            "inspect currently requires GNN artifacts. Install with: "
            "pip install \"softgnn-advisor[gnn]\""
        ) from exc
    import pandas as pd
    from softgnn_advisor.config.settings import get_project_paths

    console.rule(f"[bold cyan]Graph Inspection - Project: {project}")

    paths = get_project_paths(project)
    PYG_DATA_PATH = paths['PYG_DATA_PATH']
    NODES_DATA_PATH = paths['NODES_DATA_PATH']
    MODEL_PATH = paths['MODEL_PATH']

    # --- 1. File existence check ---
    console.print("\n[bold]--- Artifact Files ---[/bold]")
    for label, path in [
        ("nodes_data.csv", NODES_DATA_PATH),
        ("pyg_data.pt",    PYG_DATA_PATH),
        ("model.pt",       MODEL_PATH),
    ]:
        exists = "[green]FOUND[/green]" if os.path.exists(path) else "[red]MISSING[/red]"
        console.print(f"  {label:<20} {exists}  ({path})")

    if not os.path.exists(PYG_DATA_PATH):
        console.print("\n[red][ERROR] PyG data missing — run `softgnn etl` first.[/red]")
        return

    # --- 2. Node inventory ---
    console.print("\n[bold]--- Node Inventory (nodes_data.csv) ---[/bold]")
    df = pd.read_csv(NODES_DATA_PATH)
    node_counts = df['type'].value_counts()
    node_table = Table(show_header=True, header_style="bold magenta")
    node_table.add_column("Node Type", style="cyan")
    node_table.add_column("Count", justify="right", style="green")
    for ntype, cnt in node_counts.items():
        node_table.add_row(ntype, str(cnt))
    console.print(node_table)

    if 'kind' in df.columns and 'Function' in set(df['type']):
        console.print("\n[bold]--- Function Kind Inventory ---[/bold]")
        func_df = df[df['type'] == 'Function'].copy()
        kind_counts = func_df['kind'].fillna('unknown').value_counts()
        kind_table = Table(show_header=True, header_style="bold magenta")
        kind_table.add_column("Function Kind", style="cyan")
        kind_table.add_column("Count", justify="right", style="green")
        total_functions = max(len(func_df), 1)
        noisy = 0
        for kind, cnt in kind_counts.items():
            if kind in {'builtin', 'external', 'unknown'}:
                noisy += int(cnt)
            kind_table.add_row(str(kind), str(cnt))
        console.print(kind_table)
        noise_ratio = noisy / total_functions
        console.print(f"  Noise ratio (builtin/external/unknown): [cyan]{noise_ratio * 100:.1f}%[/cyan]")
        if noise_ratio > 0.5:
            console.print("  [yellow][INFO] Most Function nodes are external/builtin/unknown calls, which is normal for AST call graphs.[/yellow]")
            console.print("  Impact/triage should prioritize project-defined functions using the `kind` metadata.")

    # --- 3. Raw graph statistics ---
    console.print("\n[bold]--- Raw PyG Graph (before ToUndirected) ---[/bold]")
    data = torch.load(PYG_DATA_PATH, map_location='cpu', weights_only=False)
    console.print(f"  Total nodes : [cyan]{data.num_nodes}[/cyan]")
    console.print(f"  Total edges : [cyan]{data.num_edges}[/cyan]")
    console.print(f"  Node types  : {data.node_types}")

    edge_table = Table(show_header=True, header_style="bold magenta")
    edge_table.add_column("Edge Type (src, rel, dst)", style="yellow")
    edge_table.add_column("# Edges", justify="right", style="green")
    edge_table.add_column("Diagnosis", style="cyan")

    WARN_THRESHOLD = 5   # fewer than this = sparse / problematic

    for et in data.edge_types:
        n = data[et].edge_index.size(1)
        if et[1].startswith('rev_'):
            continue  # skip reverse edges for clarity
        diagnosis = "[green]OK[/green]" if n >= WARN_THRESHOLD else "[red]SPARSE[/red]"
        edge_table.add_row(str(et), str(n), diagnosis)

    console.print(edge_table)

    # --- 4. After ToUndirected ---
    data_u = T.ToUndirected()(data)
    console.print(f"\n[bold]After ToUndirected:[/bold] {data_u.num_edges} total edges ({len(data_u.edge_types)} types)")

    # --- 5. Developer-centric diagnosis ---
    console.print("\n[bold]--- Developer Connectivity Diagnosis ---[/bold]")
    dev_count = node_counts.get('Developer', 0)
    commit_count = node_counts.get('Commit', 0)
    console.print(f"  Developers : [cyan]{dev_count}[/cyan]")
    console.print(f"  Commits    : [cyan]{commit_count}[/cyan]")

    authored_edges = 0
    for et in data.edge_types:
        if 'authored_by' in et[1] or 'modifies' in et[1]:
            authored_edges += data[et].edge_index.size(1)
    console.print(f"  Git edges (authored_by + modifies): [cyan]{authored_edges}[/cyan]")

    if dev_count == 0:
        console.print("\n  [red][WARN] No Developer nodes found![/red]")
        console.print("  Git history may not have been parsed. Check that the --path points to a Git repo.")
    elif authored_edges < dev_count * 2:
        console.print(f"\n  [yellow][WARN] Very few Git edges per Developer ({authored_edges}/{dev_count}).[/yellow]")
        console.print("  The Triage model will underperform. Consider scanning a repo with richer commit history.")
    else:
        console.print("\n  [green][OK] Developer graph looks healthy for training.[/green]")

    # --- 6. Model status ---
    if os.path.exists(MODEL_PATH):
        size_mb = os.path.getsize(MODEL_PATH) / 1024 / 1024
        console.print(f"\n[bold]--- Trained Model ---[/bold]")
        console.print(f"  model.pt size: [cyan]{size_mb:.2f} MB[/cyan]")
        console.print(f"  [green][OK] Model is ready for inference.[/green]")
    else:
        console.print(f"\n  [yellow]No trained model yet — run `softgnn train --project {project}`[/yellow]")

    console.rule("[bold cyan]Inspection Complete")


@cli.command()
@click.option('--project', required=True, help='Project name')
@click.option('--developer', required=True, help='Developer name to explain')
def explain(project, developer):
    """Explain why a developer was recommended."""
    import pandas as pd
    try:
        import torch
    except ImportError as exc:
        raise click.ClickException(
            "explain currently requires GNN artifacts. Install with: "
            "pip install \"softgnn-advisor[gnn]\""
        ) from exc
    from collections import Counter, defaultdict
    from softgnn_advisor.config.settings import get_project_paths
    from softgnn_advisor.core.developer_aliases import load_developer_aliases, resolve_developer_identity

    console.rule(f"[bold cyan]Developer Explanation - Project: {project}")
    console.print(Panel(
        f"Developer: [bold magenta]{developer}[/bold magenta]\n"
        "Evidence source: Git graph (Developer -> Commit -> File)"
    ))

    paths = get_project_paths(project)
    PYG_DATA_PATH = paths['PYG_DATA_PATH']
    NODES_DATA_PATH = paths['NODES_DATA_PATH']

    if not os.path.exists(PYG_DATA_PATH) or not os.path.exists(NODES_DATA_PATH):
        console.print("[bold red][ERROR] Missing project data. Run ETL first.[/bold red]")
        return

    df = pd.read_csv(NODES_DATA_PATH)
    data = torch.load(PYG_DATA_PATH, map_location='cpu', weights_only=False)
    developer_aliases = load_developer_aliases(paths['DEVELOPER_ALIASES_PATH'])
    canonical_query = resolve_developer_identity(developer, '', developer_aliases).lower()
    dev_df_all = df[df['type'] == 'Developer'].copy()
    dev_df_all['canonical_name'] = dev_df_all['name'].apply(lambda n: resolve_developer_identity(str(n), '', developer_aliases))

    dev_matches = dev_df_all[
        dev_df_all['canonical_name'].str.lower().str.contains(canonical_query, case=False, na=False)
    ]

    if dev_matches.empty:
        console.print(f"[bold red][ERROR] Cannot find Developer matching '{developer}'[/bold red]")
        available = dev_df_all['canonical_name'].drop_duplicates().tolist()
        console.print("Available developers:")
        for name in available:
            console.print(f"  - {name}")
        return

    # Build quick lookup maps: (type, pyg_id) -> row
    lookup = {}
    for _, row in df.iterrows():
        lookup[(row['type'], int(row['pyg_id']))] = row

    dev_pyg_ids = set(int(x) for x in dev_matches['pyg_id'].tolist())
    authored_commits = []

    # Developer -> Commit
    edge_type = ('Developer', 'authored_by', 'Commit')
    if edge_type in data.edge_types:
        edge_index = data[edge_type].edge_index
        for src, dst in edge_index.t().tolist():
            if src in dev_pyg_ids:
                commit_row = lookup.get(('Commit', int(dst)))
                if commit_row is not None:
                    authored_commits.append({
                        'developer_pyg_id': src,
                        'commit_pyg_id': int(dst),
                        'commit_name': commit_row['name'],
                        'commit_id': commit_row['id'],
                    })

    if not authored_commits:
        console.print("[yellow]No authored commits found for this developer in graph.[/yellow]")
        return

    commit_ids = set(c['commit_pyg_id'] for c in authored_commits)
    commit_to_files = defaultdict(list)
    file_counter = Counter()

    # Commit -> File
    edge_type = ('Commit', 'modifies', 'File')
    if edge_type in data.edge_types:
        edge_index = data[edge_type].edge_index
        for src, dst in edge_index.t().tolist():
            if int(src) in commit_ids:
                file_row = lookup.get(('File', int(dst)))
                if file_row is not None:
                    file_name = str(file_row['name'])
                    file_id = str(file_row['id']).replace('FILE:', '')
                    commit_to_files[int(src)].append(file_id)
                    file_counter[file_id] += 1

    # Summary
    unique_files = len(file_counter)
    console.print(f"[bold]Summary[/bold]")
    console.print(f"  Matching developer identities : [cyan]{len(dev_matches)}[/cyan]")
    console.print(f"  Authored commits              : [cyan]{len(authored_commits)}[/cyan]")
    console.print(f"  Modified files                : [cyan]{unique_files}[/cyan]")

    # Top files table
    file_table = Table(title="Most Frequently Modified Files")
    file_table.add_column("Rank", justify="right", style="cyan")
    file_table.add_column("File", style="magenta")
    file_table.add_column("Touches", justify="right", style="green")

    for rank, (file_id, count) in enumerate(file_counter.most_common(10), start=1):
        file_table.add_row(str(rank), file_id, str(count))
    console.print(file_table)

    # Recent/evidence commits table (graph order is not guaranteed, so show first 10 collected)
    commit_table = Table(title="Evidence Commits")
    commit_table.add_column("#", justify="right", style="cyan")
    commit_table.add_column("Commit", style="yellow")
    commit_table.add_column("Touched Files", style="magenta")

    for idx, commit in enumerate(authored_commits[:10], start=1):
        files = commit_to_files.get(commit['commit_pyg_id'], [])
        files_preview = ", ".join(files[:3]) if files else "(no File edge)"
        if len(files) > 3:
            files_preview += f" ... +{len(files) - 3} more"
        commit_table.add_row(str(idx), str(commit['commit_name']), files_preview)
    console.print(commit_table)

    console.print("\n[bold green]Explanation Complete.[/bold green]")


@cli.command('doctor')
@click.option('--project', required=True, help='Project name to check')
def simple_doctor(project):
    """Check environment, metadata, and model/graph validity."""
    try:
        import torch
        import torch_geometric.transforms as T
        has_gnn_deps = True
    except ImportError:
        torch = None
        T = None
        has_gnn_deps = False
    from softgnn_advisor.config.settings import get_project_paths
    from softgnn_advisor.core.metadata_utils import compute_graph_schema_hash, load_metadata

    console.rule(f"[bold cyan]SoftGNN Doctor - Project: {project}")
    paths = get_project_paths(project)
    PYG_DATA_PATH = paths['PYG_DATA_PATH']
    NODES_DATA_PATH = paths['NODES_DATA_PATH']
    MODEL_PATH = paths['MODEL_PATH']
    METADATA_PATH = paths['METADATA_PATH']

    def ok(msg): console.print(f"[green][OK][/green] {msg}")
    def warn(msg): console.print(f"[yellow][WARN][/yellow] {msg}")
    def err(msg): console.print(f"[red][ERROR][/red] {msg}")

    ok(f"Python: {sys.version.split()[0]}")
    if has_gnn_deps:
        ok(f"Torch: {torch.__version__}")
        if torch.cuda.is_available():
            ok(f"CUDA available: {torch.cuda.get_device_name(0)}")
        else:
            warn("CUDA not available; CPU mode will be used")
    else:
        warn("GNN dependencies not installed; deterministic/core features are available")
        warn("Install GNN extras with: pip install \"softgnn-advisor\\[gnn]\"")

    for label, path in [
        ('nodes_data.csv', NODES_DATA_PATH),
        ('pyg_data.pt', PYG_DATA_PATH),
        ('model.pt', MODEL_PATH),
        ('metadata.json', METADATA_PATH),
    ]:
        if os.path.exists(path):
            ok(f"{label} found")
        else:
            warn(f"{label} missing: {path}")

    metadata = load_metadata(METADATA_PATH)
    if not metadata:
        warn("metadata.json is missing or unreadable. Run ETL again to create metadata.")
    else:
        ok(f"ETL metadata loaded. Schema hash: {metadata.get('schema_hash', 'N/A')}")
        if metadata.get('train_finished_at'):
            ok(f"Training metadata found. Test AUC: {metadata.get('test_auc', 'N/A')}")
        else:
            warn("No training metadata found. Run setup --train after installing GNN extras if you need GNN ranking.")

    if os.path.exists(PYG_DATA_PATH) and has_gnn_deps:
        try:
            data = torch.load(PYG_DATA_PATH, map_location='cpu', weights_only=False)
            current_hash = compute_graph_schema_hash(data)
            model_current_hash = compute_graph_schema_hash(T.ToUndirected()(data))
            ok(f"Current graph loaded: {data.num_nodes} nodes, {data.num_edges} edges")
            ok(f"Current raw schema hash: {current_hash}")
            ok(f"Current training/inference schema hash: {model_current_hash}")

            if metadata.get('schema_hash') and metadata.get('schema_hash') != current_hash:
                warn("metadata schema_hash differs from current graph. Run ETL again.")
            if metadata.get('model_schema_hash'):
                if metadata['model_schema_hash'] == model_current_hash:
                    ok("model schema hash matches current training/inference graph")
                else:
                    err("model schema hash does NOT match current graph. Re-run train.")

            devs = int(data['Developer'].num_nodes) if 'Developer' in data.node_types else 0
            commits = int(data['Commit'].num_nodes) if 'Commit' in data.node_types else 0
            files = int(data['File'].num_nodes) if 'File' in data.node_types else 0
            modifies = 0
            if ('Commit', 'modifies', 'File') in data.edge_types:
                modifies = int(data[('Commit', 'modifies', 'File')].edge_index.size(1))
            ok(f"Graph inventory: {devs} developers, {commits} commits, {files} files, {modifies} commit-file edges")
            if devs == 0 or commits == 0:
                warn("Developer/Commit graph is empty; triage will be weak")
            if modifies < 10:
                warn("Commit -> File edges are sparse; Git ownership will be weak")
        except Exception as e:
            err(f"Could not load pyg_data.pt: {e}")
    elif os.path.exists(PYG_DATA_PATH) and not has_gnn_deps:
        warn("pyg_data.pt exists but cannot be inspected without GNN dependencies")
    else:
        warn("pyg_data.pt missing; this is expected for core-only setup without GNN extras")

    if not os.environ.get('HF_TOKEN'):
        warn("HF_TOKEN not set; HuggingFace downloads may be slower or rate-limited")

    console.rule("[bold cyan]Doctor Complete")


def _default_project_name(repo_path):
    return os.path.basename(os.path.abspath(repo_path).rstrip(os.sep)) or 'default'


def _repo_path_for_project(project):
    from softgnn_advisor.config.settings import get_project_paths
    from softgnn_advisor.core.metadata_utils import load_metadata
    metadata = load_metadata(get_project_paths(project)['METADATA_PATH'])
    repo_path = metadata.get('source_path')
    if not repo_path:
        raise click.ClickException(f"No source_path found for project '{project}'. Run: python softgnn.py setup C:\\path\\to\\repo --project {project}")
    if not os.path.exists(repo_path):
        raise click.ClickException(f"Stored source_path does not exist for project '{project}': {repo_path}")
    return repo_path


def _render_generation(agent, result):
    markdown = agent.render_markdown(result)
    console.print(Markdown(markdown, code_theme='monokai'))
    if result.files_written:
        console.print(f"[bold green]Wrote {len(result.files_written)} test file(s).[/bold green]")
    return markdown


def _render_apply_result(result):
    """Print a compact apply summary — no plan table reprint."""
    kept = [f for f in (getattr(result, 'files_written', None) or [])]
    rolled = [v for v in (getattr(result, 'failures', None) or []) if isinstance(v, dict) and v.get('rolled_back')]
    repairs = getattr(result, 'repair_attempts', None) or []

    summary = Table(title="Apply Result")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="green")
    summary.add_row("Targets attempted", str(len(getattr(result, 'plans', None) or [])))
    summary.add_row("Blocks kept", str(len(kept)))
    summary.add_row("Blocks rolled back", str(len(rolled)))
    summary.add_row("Repair attempts", str(len(repairs)))
    pytest_returncode = getattr(result, 'pytest_returncode', None)
    if pytest_returncode is not None:
        status = "[green]PASS[/green]" if pytest_returncode == 0 else "[red]FAIL[/red]"
        summary.add_row("Pytest final", status)
    verification_results = getattr(result, 'verification_results', None) or []
    proof_pass = sum(1 for item in verification_results if getattr(item, 'proof_status', 'skipped') == 'pass')
    proof_fail = sum(1 for item in verification_results if getattr(item, 'proof_status', 'skipped') == 'fail')
    proof_skipped = sum(1 for item in verification_results if getattr(item, 'proof_status', 'skipped') == 'skipped')
    if proof_pass or proof_fail:
        summary.add_row("Runtime proof PASS", str(proof_pass))
        summary.add_row("Runtime proof FAIL", str(proof_fail))
        if proof_skipped:
            summary.add_row("Runtime proof skipped", str(proof_skipped))
    runtime_result = getattr(result, 'runtime_result', None)
    if runtime_result:
        summary.add_row("Runtime edges", str(len(runtime_result.runtime_edges)))
    pre_missing_count = getattr(result, 'pre_missing_count', None)
    post_missing_count = getattr(result, 'post_missing_count', None)
    if pre_missing_count is not None and post_missing_count is not None:
        delta = pre_missing_count - post_missing_count
        summary.add_row("Missing coverage delta", f"-{delta}" if delta >= 0 else f"+{abs(delta)}")
    console.print(summary)
    warnings = getattr(result, 'warnings', None) or []
    if warnings:
        unique_warnings = []
        seen = set()
        for w in warnings:
            if w not in seen:
                unique_warnings.append(w)
                seen.add(w)
        for w in unique_warnings[:5]:
            console.print(f"[yellow]{w}[/yellow]")
        if len(unique_warnings) > 5:
            console.print(f"[yellow]... and {len(unique_warnings) - 5} more warnings[/yellow]")


def _save_and_show_report(project, payload, open_report=False):
    from pathlib import Path
    import webbrowser
    from softgnn_advisor.core.report_renderer import save_html_report

    report_path, latest_path = save_html_report(project, payload)
    console.print(f"[bold green]Report saved:[/bold green] {latest_path}")
    console.print("[cyan]Open it to review PR impact, generated tests, and runtime proof.[/cyan]")
    if open_report:
        webbrowser.open(Path(latest_path).resolve().as_uri())
    return report_path, latest_path


def _run_read_only_scan(scanner, project, repo_path, base, head, mode='hybrid', gnn_types='File,Class,Function', max_impact=30, max_reviewers=3, suggest_tests=True, change_source='auto', smart=True, fallback_full_scan=False):
    result = scanner.scan(base=base, head=head, mode=mode, gnn_types=gnn_types, max_impact=max_impact, max_reviewers=max_reviewers, suggest_tests=suggest_tests, change_source=change_source)
    effective_base, effective_head, effective_source = base, head, change_source
    if result.changed_files or change_source != 'auto' or not smart:
        return result, effective_base, effective_head, effective_source

    from softgnn_advisor.core.scan_fallback import resolve_read_only_scan_range
    decision = resolve_read_only_scan_range(repo_path, base=base, head=head)
    for message in decision.messages:
        console.print(f"[yellow]{message}[/yellow]")
    if decision.fallback_used and decision.changed_files:
        effective_base, effective_head, effective_source = decision.base, decision.head, 'git'
        result = scanner.scan(base=effective_base, head=effective_head, mode=mode, gnn_types=gnn_types, max_impact=max_impact, max_reviewers=max_reviewers, suggest_tests=suggest_tests, change_source='git')
        result.warnings.insert(0, f"Smart scan fallback used: {decision.reason} ({effective_base[:7]}...{effective_head}).")
        return result, effective_base, effective_head, effective_source

    fs_result = scanner.scan(base=base, head=head, mode=mode, gnn_types=gnn_types, max_impact=max_impact, max_reviewers=max_reviewers, suggest_tests=suggest_tests, change_source='filesystem')
    if fs_result.changed_files:
        fs_result.warnings.insert(0, 'Smart scan fallback used: filesystem snapshot diff.')
        return fs_result, base, head, 'filesystem'

    if fallback_full_scan:
        full_result = scanner.scan(base=base, head=head, mode=mode, gnn_types=gnn_types, max_impact=max_impact, max_reviewers=max_reviewers, suggest_tests=suggest_tests, change_source='full-scan')
        full_result.warnings.insert(0, 'Smart scan fallback used: full project scan.')
        return full_result, base, head, 'full-scan'

    _print_zero_diff_hint(project, base, head)
    return result, effective_base, effective_head, effective_source


def _print_zero_diff_hint(project, base, head):
    console.print(Panel(
        "[bold yellow]No changed files were found for this scan.[/bold yellow]\n\n"
        f"SoftGNN scanned [cyan]{base}...{head}[/cyan]. If you just pulled shared changes and want SoftGNN memory updated, run:\n"
        f"  [cyan]softgnn refresh --project {project}[/cyan]\n\n"
        "Other useful commands:\n"
        f"  [cyan]softgnn pr-scan --project {project} --base HEAD~1 --head HEAD[/cyan]  # scan the latest commit\n"
        f"  [cyan]softgnn pr-scan --project {project} --change-source filesystem[/cyan]    # scan local uncommitted file changes\n"
        f"  [cyan]softgnn pr-scan --project {project} --change-source full-scan[/cyan]     # scan the full project",
        title="Zero-diff hint",
        border_style="yellow",
    ))


@cli.command('setup')
@click.argument('repo_path')
@click.option('--project', default=None, help='Project name; defaults to repository folder name')
@click.option('--train/--no-train', default=False, show_default=True, help='Run experimental HGT training after graph build')
def simple_setup(repo_path, project, train):
    """Beginner setup: build graph and filesystem snapshot."""
    project = project or _default_project_name(repo_path)
    console.rule(f"[bold cyan]SoftGNN Setup - Project: {project}")
    from softgnn_advisor.scripts.etl_run import run_etl_pipeline
    from softgnn_advisor.core.change_provider import build_filesystem_snapshot, save_filesystem_snapshot, snapshot_path_for_project

    run_etl_pipeline(repo_path, project)
    snapshot = build_filesystem_snapshot(repo_path)
    save_filesystem_snapshot(snapshot_path_for_project(project), snapshot)
    console.print("[bold green]Graph and filesystem snapshot saved.[/bold green]")
    if train:
        try:
            from softgnn_advisor.scripts.train_model import run_optimization
        except ImportError as exc:
            raise click.ClickException(
                "Training requires GNN dependencies. Install with: pip install \"softgnn-advisor[gnn]\" "
                "or pip install \"softgnn-advisor[all]\""
            ) from exc
        run_optimization(project)
        console.print("[bold green]Training completed.[/bold green]")
    else:
        console.print("[yellow]Training skipped. Use --train if you want experimental GNN ranking.[/yellow]")


@cli.command('refresh')
@click.option('--project', required=True, help='Project name created by setup/prepare')
@click.option('--repo-path', default=None, help='Optional override; otherwise read from project metadata')
@click.option('--train/--no-train', default=False, show_default=True, help='Run experimental HGT training after refresh')
@click.option('--runtime/--no-runtime', default=False, show_default=True, help='Refresh pytest runtime coverage after graph rebuild')
@click.option('--pytest', 'pytest_args', default='tests', show_default=True, help='Arguments passed to pytest for --runtime')
def simple_refresh(project, repo_path, train, runtime, pytest_args):
    """Refresh SoftGNN graph and filesystem snapshot for the current checkout."""
    repo_path = repo_path or _repo_path_for_project(project)
    console.rule(f"[bold cyan]SoftGNN Refresh - Project: {project}")
    console.print(f"Repository: [yellow]{os.path.abspath(repo_path)}[/yellow]")

    from softgnn_advisor.scripts.etl_run import run_etl_pipeline
    from softgnn_advisor.core.change_provider import build_filesystem_snapshot, save_filesystem_snapshot, snapshot_path_for_project

    console.print("[cyan]Updating knowledge graph...[/cyan]")
    run_etl_pipeline(repo_path, project)
    console.print("[cyan]Updating filesystem snapshot...[/cyan]")
    snapshot = build_filesystem_snapshot(repo_path)
    save_filesystem_snapshot(snapshot_path_for_project(project), snapshot)
    console.print("[bold green]Graph and filesystem snapshot refreshed.[/bold green]")

    if runtime:
        console.print("[cyan]Refreshing runtime coverage map...[/cyan]")
        from softgnn_advisor.infrastructure.pipelines.runtime_coverage_mapper import RuntimeCoverageMapper
        runtime_result = RuntimeCoverageMapper(project, repo_path=repo_path).map_runtime_coverage(pytest_args=pytest_args, mode='per-test', persist=True)
        console.print(f"[bold green]Runtime mapping refreshed:[/bold green] {len(runtime_result.runtime_edges)} edge(s)")

    if train:
        try:
            from softgnn_advisor.scripts.train_model import run_optimization
        except ImportError as exc:
            raise click.ClickException(
                "Training requires GNN dependencies. Install with: pip install \"softgnn-advisor[gnn]\" "
                "or pip install \"softgnn-advisor[all]\""
            ) from exc
        run_optimization(project)
        console.print("[bold green]Training completed.[/bold green]")

@cli.command('dashboard')
@click.option('--project', required=True, help='Project name created by setup/prepare')
@click.option('--repo-path', default=None, help='Optional override; otherwise read from project metadata')
@click.option('--host', default='127.0.0.1', show_default=True, help='Dashboard bind host; keep localhost for safety')
@click.option('--port', default=8765, show_default=True, help='Dashboard port')
@click.option('--open', 'open_dashboard', is_flag=True, help='Open the dashboard in a browser')
def dashboard(project, repo_path, host, port, open_dashboard):
    """Start the local interactive SoftGNN dashboard."""
    repo_path = repo_path or _repo_path_for_project(project)
    if host not in {'127.0.0.1', 'localhost'}:
        raise click.ClickException('For safety, dashboard currently only supports 127.0.0.1/localhost.')
    from softgnn_advisor.core.dashboard_server import start_dashboard
    start_dashboard(project, repo_path, host=host, port=port, open_browser=open_dashboard)


@cli.command('scan')
@click.option('--project', required=True, help='Project name created by setup/prepare')
@click.option('--repo-path', default=None, help='Optional override; otherwise read from project metadata')
@click.option('--base', default='main', show_default=True)
@click.option('--head', default='HEAD', show_default=True)
@click.option('--source', type=click.Choice(['auto', 'git', 'filesystem', 'full-scan']), default='auto', show_default=True)
@click.option('--mode', type=click.Choice(['deterministic', 'hybrid', 'gnn']), default='hybrid', show_default=True)
@click.option('--max-impact', default=30, show_default=True)
@click.option('--smart/--no-smart', default=True, show_default=True, help='Use safe read-only fallback when the default diff is empty')
@click.option('--fallback-full-scan', is_flag=True, help='If smart scan finds no git/filesystem changes, scan the full project')
def simple_scan(project, repo_path, base, head, source, mode, max_impact, smart, fallback_full_scan):
    """Beginner scan: detect changes and suggest coverage targets without LLM calls."""
    repo_path = repo_path or _repo_path_for_project(project)
    console.print("[cyan]LLM: not used | Writes: none | Pytest: not run[/cyan]")
    from softgnn_advisor.core.pr_scanner import PRScanner
    from softgnn_advisor.core.scan_cache import save_scan_bundle
    scanner = PRScanner(project, repo_path=repo_path)
    result, effective_base, effective_head, effective_source = _run_read_only_scan(
        scanner,
        project,
        scanner.repo_path,
        base,
        head,
        mode=mode,
        max_impact=max_impact,
        change_source=source,
        smart=smart,
        fallback_full_scan=fallback_full_scan,
    )
    scan_path, latest_path, bundle = save_scan_bundle(project, result, repo_path, base=effective_base, head=effective_head, change_source=effective_source, mode=mode)
    for warning in result.warnings:
        console.print(f"[yellow]{warning}[/yellow]")
    summary = Table(title="Scan Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="green")
    summary.add_row("Project", project)
    summary.add_row("Change source", result.change_source)
    summary.add_row("Changed files", str(len(result.changed_files)))
    summary.add_row("Changed nodes", str(len(result.changed_nodes)))
    summary.add_row("Missing coverage", str(len(result.missing_coverage)))
    summary.add_row("Suggested tests", str(len(result.suggested_tests)))
    console.print(summary)
    console.print(f"[bold green]Scan saved:[/bold green] {scan_path}")
    console.print(f"[bold green]Latest scan:[/bold green] {latest_path}")
    console.print(f"Next: [cyan]softgnn plan --project {project}[/cyan]")


@cli.command('plan')
@click.option('--project', required=True, help='Project name created by setup/prepare')
@click.option('--repo-path', default=None, help='Optional override; otherwise read from project metadata')
@click.option('--base', default='main', show_default=True)
@click.option('--head', default='HEAD', show_default=True)
@click.option('--target', default=None, help='Target id, e.g. FUNC:foo')
@click.option('--file', 'source_file', default=None, help='Source file for explicit target')
@click.option('--only-file', default=None, help='Generate only for targets in this source file')
@click.option('--max-targets', default=3, show_default=True)
@click.option('--strategy', type=click.Choice(['template', 'llm', 'auto']), default='llm', show_default=True)
@click.option('--no-llm', is_flag=True, help='Do not call LLM; generate template tests')
@click.option('--source', type=click.Choice(['auto', 'git', 'filesystem', 'full-scan']), default='auto', show_default=True)
@click.option('--llm-required/--llm-fallback', default=True, show_default=True)
@click.option('--save-plan/--no-save-plan', default=True, show_default=True)
@click.option('--scan', 'scan_ref', default='latest', show_default=True, help='Saved scan id/path to plan from; defaults to latest')
@click.option('--refresh-scan', is_flag=True, help='Run a fresh scan before planning')
@click.option('--force-stale-scan', is_flag=True, help='Plan from a stale saved scan')
def simple_plan(project, repo_path, base, head, target, source_file, only_file, max_targets, strategy, no_llm, source, llm_required, save_plan, scan_ref, refresh_scan, force_stale_scan):
    """Beginner plan: scan, generate proposed tests with LLM by default, and save a reusable plan bundle."""
    repo_path = repo_path or _repo_path_for_project(project)
    if no_llm:
        strategy = 'template'
        llm_required = False
    console.print("[cyan]Workflow: scan snapshot -> plan | LLM: enabled by default | Writes: plan cache only | Pytest: not run[/cyan]")
    from softgnn_advisor.core.test_generation_agent import TestGenerationAgent
    from softgnn_advisor.core.plan_cache import save_plan_bundle
    from softgnn_advisor.core.pr_scanner import PRScanner
    from softgnn_advisor.core.scan_cache import load_scan_bundle, save_scan_bundle, scan_bundle_to_result, validate_scan_bundle
    if refresh_scan:
        console.print("[cyan]Stage SCAN: refreshing scan because --refresh-scan was set.[/cyan]")
        scanner = PRScanner(project, repo_path=repo_path)
        scan_result = scanner.scan(base=base, head=head, mode='hybrid', max_impact=30, change_source=source)
        scan_path, _, scan_bundle = save_scan_bundle(project, scan_result, repo_path, base=base, head=head, change_source=source, mode='hybrid')
    else:
        try:
            scan_bundle, scan_path = load_scan_bundle(project, scan_ref)
            validation = validate_scan_bundle(scan_bundle, repo_path)
            if not validation['valid'] and not force_stale_scan:
                for warning in validation['warnings']:
                    console.print(f"[yellow]{warning}[/yellow]")
                console.print("[yellow]Saved scan is stale; auto-scanning fresh before planning.[/yellow]")
                scanner = PRScanner(project, repo_path=repo_path)
                scan_result = scanner.scan(base=base, head=head, mode='hybrid', max_impact=30, change_source=source)
                scan_path, _, scan_bundle = save_scan_bundle(project, scan_result, repo_path, base=base, head=head, change_source=source, mode='hybrid')
            else:
                if not validation['valid']:
                    for warning in validation['warnings']:
                        console.print(f"[yellow]{warning}[/yellow]")
                    console.print("[yellow]Using stale scan because --force-stale-scan was set.[/yellow]")
                scan_result = scan_bundle_to_result(scan_bundle)
                console.print(f"[bold green]Loaded saved scan:[/bold green] {scan_path}")
        except FileNotFoundError:
            console.print("[cyan]Stage SCAN: no saved scan found; auto-scanning first.[/cyan]")
            scanner = PRScanner(project, repo_path=repo_path)
            scan_result = scanner.scan(base=base, head=head, mode='hybrid', max_impact=30, change_source=source)
            scan_path, _, scan_bundle = save_scan_bundle(project, scan_result, repo_path, base=base, head=head, change_source=source, mode='hybrid')
    agent = TestGenerationAgent(project, repo_path=repo_path)
    result = agent.plan_from_scan(
        scan_result,
        base=base,
        head=head,
        mode='plan',
        max_targets=max_targets,
        target_id=target,
        source_file=source_file,
        only_file=only_file,
        refresh_runtime=False,
        generation_strategy=strategy,
        llm_required=llm_required,
        change_source=source,
    )
    _render_generation(agent, result)
    if save_plan and result.plans:
        plan_path, latest_path, _ = save_plan_bundle(project, result, repo_path, base=base, head=head, change_source=source, llm_config=agent.llm_config, scan_id=scan_bundle.get('scan_id'), scan_path=scan_path, scan_fingerprint=scan_bundle.get('repo_fingerprint'))
        console.print(f"[bold green]Plan saved:[/bold green] {plan_path}")
        console.print(f"[bold green]Latest plan:[/bold green] {latest_path}")
        console.print(f"Next: [cyan]python softgnn.py apply --project {project}[/cyan]")


@cli.command('generate')
@click.option('--project', required=True, help='Project name created by setup/prepare')
@click.option('--repo-path', default=None, help='Optional override; otherwise read from project metadata')
@click.option('--base', default='main', show_default=True)
@click.option('--head', default='HEAD', show_default=True)
@click.option('--target', default=None, help='Target id, e.g. FUNC:foo')
@click.option('--file', 'source_file', default=None, help='Source file for explicit target')
@click.option('--only-file', default=None, help='Generate only for targets in this source file')
@click.option('--max-targets', default=3, show_default=True)
@click.option('--strategy', type=click.Choice(['template', 'llm', 'auto']), default='llm', show_default=True)
@click.option('--no-llm', is_flag=True, help='Do not call LLM; generate template tests')
@click.option('--llm-provider', default=None, help='LLM provider override, e.g. openai-compatible')
@click.option('--llm-model', default=None, help='LLM model override')
@click.option('--llm-base-url', default=None, help='LLM base URL override')
@click.option('--llm-api-key-env', default=None, help='Name of env var containing the LLM API key')
@click.option('--llm-required/--llm-fallback', default=False, show_default=True, help='Fail if LLM is unavailable instead of falling back to templates')
@click.option('--llm-temperature', default=0.1, show_default=True, help='LLM temperature')
@click.option('--llm-max-tokens', default=4096, show_default=True, help='LLM max output tokens')
@click.option('--source', type=click.Choice(['auto', 'git', 'filesystem', 'full-scan']), default='auto', show_default=True)
@click.option('--repair', default=2, show_default=True, help='Local repair attempts per failing generated block before block rollback')
@click.option('--replan-iters', default=1, show_default=True, help='Re-plan rolled-back/failed targets after apply feedback')
@click.option('--pytest', 'pytest_args', default=None, help='Override pytest args')
@click.option('--keep-failing-tests/--rollback-failing-tests', default=False, show_default=True)
@click.option('--partial-rollback/--batch-rollback', default=True, show_default=True, help='Keep passing generated tests and roll back only failing generated tests')
@click.option('--pytest-stream/--no-pytest-stream', default=True, show_default=True, help='Stream pytest output while verification runs')
@click.option('--require-runtime-proof/--no-require-runtime-proof', default=True, show_default=True, help='Rollback generated block if no runtime edge to target is proven after pytest pass')
@click.option('--report/--no-report', default=True, show_default=True, help='Write a static HTML proof report after generate')
@click.option('--open-report', is_flag=True, help='Open the generated HTML report in a browser')
@click.option('--yes', 'assume_yes', is_flag=True, help='Accept safe interactive prompts, such as using HEAD~1...HEAD after a same-branch commit')
def simple_generate(project, repo_path, base, head, target, source_file, only_file, max_targets, strategy, no_llm, llm_provider, llm_model, llm_base_url, llm_api_key_env, llm_required, llm_temperature, llm_max_tokens, source, repair, replan_iters, pytest_args, keep_failing_tests, partial_rollback, pytest_stream, require_runtime_proof, report, open_report, assume_yes):
    """Beginner generate: run scan, plan, save it, then apply that saved plan."""
    repo_path = repo_path or _repo_path_for_project(project)
    console.print("[cyan]Workflow: scan -> plan -> apply | Replan: plan -> apply using same scan | Pytest: yes | Runtime map: yes[/cyan]")
    from softgnn_advisor.core.pr_scanner import PRScanner
    from softgnn_advisor.core.scan_cache import save_scan_bundle
    from softgnn_advisor.core.test_generation_agent import TestGenerationAgent
    from softgnn_advisor.core.plan_cache import bundle_to_generation_plans, save_plan_bundle
    if no_llm:
        strategy = 'template'
        llm_required = False
    else:
        llm_required = True if strategy == 'llm' else llm_required
    llm_api_key = os.getenv(llm_api_key_env) if llm_api_key_env else None
    agent = TestGenerationAgent(
        project,
        repo_path=repo_path,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
    )

    agent.print_stage('SCAN', 'Fresh scan for generate workflow')
    scanner = PRScanner(project, repo_path=repo_path)
    scan_result = scanner.scan(base=base, head=head, mode='hybrid', max_impact=30, change_source=source)
    scan_path, latest_scan_path, scan_bundle = save_scan_bundle(project, scan_result, repo_path, base=base, head=head, change_source=source, mode='hybrid')

    # --- Scan summary ---------------------------------------------------------
    for warning in scan_result.warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    scan_summary = Table(title="Scan Summary")
    scan_summary.add_column("Metric", style="cyan")
    scan_summary.add_column("Value", style="green")
    scan_summary.add_row("Change source", scan_result.change_source)
    scan_summary.add_row("Changed files", str(len(scan_result.changed_files)))
    scan_summary.add_row("Changed graph nodes", str(len(scan_result.changed_nodes)))
    scan_summary.add_row("Missing coverage targets", str(len(scan_result.missing_coverage)))
    scan_summary.add_row("Related existing tests", str(len(scan_result.related_tests)))
    console.print(scan_summary)

    if not scan_result.changed_files and source in ('auto', 'git'):
        from softgnn_advisor.core.scan_fallback import generate_same_branch_fallback
        decision = generate_same_branch_fallback(scanner.repo_path, base=base, head=head)
        for message in decision.messages:
            console.print(f"[yellow]{message}[/yellow]")
        if decision.reason == 'dirty-worktree':
            console.print(Panel(
                "For reproducible generated tests, commit your code first:\n"
                "  [cyan]git add .[/cyan]\n"
                "  [cyan]git commit -m \"your change\"[/cyan]\n"
                f"  [cyan]softgnn generate --project {project}[/cyan]\n\n"
                "Or explicitly generate from local file changes:\n"
                f"  [cyan]softgnn generate --project {project} --source filesystem[/cyan]",
                title="Commit before generate",
                border_style="yellow",
            ))
            return
        if decision.reason == 'same-branch-commit':
            use_fallback = assume_yes or click.confirm("Use HEAD~1...HEAD for this generate run?", default=False)
            if not use_fallback:
                console.print("[yellow]Generate stopped. Re-run with --base HEAD~1 --head HEAD or --yes if this is intentional.[/yellow]")
                return
            base, head, source = decision.base, decision.head, 'git'
            console.print(f"[bold green]Using generate range {base}...{head}.[/bold green]")
            scan_result = scanner.scan(base=base, head=head, mode='hybrid', max_impact=30, change_source=source)
            scan_path, latest_scan_path, scan_bundle = save_scan_bundle(project, scan_result, repo_path, base=base, head=head, change_source=source, mode='hybrid')
            for warning in scan_result.warnings:
                console.print(f"[yellow]{warning}[/yellow]")
        else:
            console.print(Panel(
                "Generate did not fallback automatically because it writes tests.\n\n"
                f"If you just pulled shared changes, refresh SoftGNN memory:\n  [cyan]softgnn refresh --project {project}[/cyan]\n\n"
                f"If you intentionally want tests for the latest commit:\n  [cyan]softgnn generate --project {project} --base HEAD~1 --head HEAD[/cyan]\n\n"
                f"If you want tests for local uncommitted changes:\n  [cyan]softgnn generate --project {project} --source filesystem[/cyan]",
                title="No generate diff",
                border_style="yellow",
            ))

    if scan_result.changed_nodes:
        nodes_table = Table(title="Changed Nodes")
        nodes_table.add_column("#", justify="right", style="cyan", width=4)
        nodes_table.add_column("Type", style="blue", width=10)
        nodes_table.add_column("ID", style="magenta")
        nodes_table.add_column("File", style="white")
        for idx, node in enumerate(scan_result.changed_nodes[:10], start=1):
            nodes_table.add_row(str(idx), node.node_type, node.full_id, node.source_file)
        if len(scan_result.changed_nodes) > 10:
            nodes_table.add_row("...", "", f"... and {len(scan_result.changed_nodes) - 10} more", "")
        console.print(nodes_table)

    if scan_result.missing_coverage:
        missing_table = Table(title="Missing Coverage Targets")
        missing_table.add_column("#", justify="right", style="cyan", width=4)
        missing_table.add_column("Target", style="yellow")
        missing_table.add_column("Reason", style="white")
        for idx, mc in enumerate(scan_result.missing_coverage[:8], start=1):
            missing_table.add_row(str(idx), mc.target_id, getattr(mc, 'reason', ''))
        if len(scan_result.missing_coverage) > 8:
            missing_table.add_row("...", f"... and {len(scan_result.missing_coverage) - 8} more", "")
        console.print(missing_table)


    console.print(f"[bold green]Scan saved:[/bold green] {scan_path}")
    console.print(f"[bold green]Latest scan:[/bold green] {latest_scan_path}")
    # --------------------------------------------------------------------------


    agent.print_stage('PLAN', 'Generating plan from saved scan')
    plan_result = agent.plan_from_scan(
        scan_result,
        base=base,
        head=head,
        mode='plan',
        max_targets=max_targets,
        target_id=target,
        source_file=source_file,
        only_file=only_file,
        verify=False,
        repair_iters=0,
        refresh_runtime=False,
        generation_strategy=strategy,
        llm_required=llm_required,
        llm_temperature=llm_temperature,
        llm_max_tokens=llm_max_tokens,
        change_source=source,
    )
    _render_generation(agent, plan_result)
    if not plan_result.plans:
        console.print("[yellow]No plans were generated; apply skipped.[/yellow]")
        return
    plan_path, latest_path, bundle = save_plan_bundle(project, plan_result, repo_path, base=base, head=head, change_source=source, llm_config=agent.llm_config, scan_id=scan_bundle.get('scan_id'), scan_path=scan_path, scan_fingerprint=scan_bundle.get('repo_fingerprint'))
    console.print(f"[bold green]Plan saved:[/bold green] {plan_path}")
    console.print(f"[bold green]Latest plan:[/bold green] {latest_path}")

    agent.print_stage('APPLY', 'Applying saved plan and verifying generated blocks')
    result = agent.apply_saved_plans(
        bundle_to_generation_plans(bundle),
        base=base,
        head=head,
        verify=True,
        repair_iters=repair,
        refresh_runtime=True,
        runtime_mode='per-test',
        confirm_pr_scan=False,
        keep_failing_tests=keep_failing_tests,
        pytest_args=pytest_args,
        generation_strategy=strategy,
        llm_required=llm_required,
        llm_temperature=llm_temperature,
        llm_max_tokens=llm_max_tokens,
        change_source=source,
        partial_rollback=partial_rollback,
        pytest_stream=pytest_stream,
        require_runtime_proof=require_runtime_proof,
    )
    _render_apply_result(result)
    for iteration in range(1, max(0, int(replan_iters or 0)) + 1):
        feedback = agent._apply_feedback_from_result(result)
        if not feedback:
            console.print("[green]No failed targets remain; replan loop complete.[/green]")
            break
        from softgnn_advisor.core.failure_classifier import replanable_failures
        source_by_target = {plan.target_id: plan.source_file for plan in getattr(result, 'plans', [])}
        allowed, blocked = replanable_failures(getattr(result, 'verification_results', []), source_by_target)
        for target_id, category, reason in blocked:
            console.print(f"[yellow]Skipping replan for {target_id}: {category} — {reason}[/yellow]")
        feedback = {target_id: item for target_id, item in feedback.items() if target_id in allowed}
        if not feedback:
            console.print("[yellow]Replan skipped: remaining failures look like environment/source/runtime issues, not generated-test quality issues.[/yellow]")
            break
        agent.print_stage('REPLAN', f'Planning {len(feedback)} failed target(s), iteration {iteration}/{replan_iters}, using same scan')
        retry_results = []
        for target_id, item in feedback.items():
            retry_result = agent.plan_from_scan(
                scan_result,
                base=base,
                head=head,
                mode='plan',
                max_targets=1,
                target_id=target_id,
                source_file=item.get('source_file'),
                verify=False,
                repair_iters=0,
                refresh_runtime=False,
                generation_strategy=strategy,
                llm_required=llm_required,
                llm_temperature=llm_temperature,
                llm_max_tokens=llm_max_tokens,
                change_source=source,
                failure_feedback=feedback,
            )
            retry_results.append(retry_result)
        retry_plans = [plan for retry_result in retry_results for plan in retry_result.plans]
        if not retry_plans:
            console.print("[yellow]No retry plans were generated; stopping replan loop.[/yellow]")
            break
        retry_result_for_save = retry_results[0]
        retry_result_for_save.plans = retry_plans
        retry_plan_path, retry_latest_path, retry_bundle = save_plan_bundle(project, retry_result_for_save, repo_path, base=base, head=head, change_source=source, llm_config=agent.llm_config, scan_id=scan_bundle.get('scan_id'), scan_path=scan_path, scan_fingerprint=scan_bundle.get('repo_fingerprint'))
        console.print(f"[bold green]Retry plan saved:[/bold green] {retry_plan_path}")
        console.print(f"[bold green]Latest plan:[/bold green] {retry_latest_path}")
        agent.print_stage('APPLY', f'Applying retry plan {iteration}/{replan_iters}')
        result = agent.apply_saved_plans(
            bundle_to_generation_plans(retry_bundle),
            base=base,
            head=head,
            verify=True,
            repair_iters=repair,
            refresh_runtime=True,
            runtime_mode='per-test',
            confirm_pr_scan=False,
            keep_failing_tests=keep_failing_tests,
            pytest_args=pytest_args,
            generation_strategy=strategy,
            llm_required=llm_required,
            llm_temperature=llm_temperature,
            llm_max_tokens=llm_max_tokens,
            change_source=source,
            partial_rollback=partial_rollback,
            pytest_stream=pytest_stream,
            require_runtime_proof=require_runtime_proof,
        )
        _render_apply_result(result)
    if report:
        from softgnn_advisor.core.report_renderer import build_generate_report_payload
        payload = build_generate_report_payload(
            project=project,
            scan_result=scan_result,
            plan_result=plan_result,
            apply_result=result,
            repo_path=repo_path,
        )
        _save_and_show_report(project, payload, open_report=open_report)


@cli.command('apply')
@click.option('--project', required=True, help='Project name created by setup/prepare')
@click.option('--repo-path', default=None, help='Optional override; otherwise read from project metadata')
@click.option('--base', default='main', show_default=True)
@click.option('--head', default='HEAD', show_default=True)
@click.option('--plan', 'plan_ref', default=None, help='Plan id or path; defaults to latest saved plan')
@click.option('--ignore-plan', is_flag=True, help='Generate fresh instead of using a saved plan')
@click.option('--force-stale-plan', is_flag=True, help='Apply saved plan even if source files changed')
@click.option('--target', default=None, help='Target id for fresh generation')
@click.option('--file', 'source_file', default=None, help='Source file for explicit target')
@click.option('--max-targets', default=3, show_default=True)
@click.option('--strategy', type=click.Choice(['template', 'llm', 'auto']), default='llm', show_default=True)
@click.option('--no-llm', is_flag=True, help='Do not call LLM when generating fresh because no saved plan exists')
@click.option('--llm-provider', default=None, help='LLM provider override, e.g. openai-compatible')
@click.option('--llm-model', default=None, help='LLM model override')
@click.option('--llm-base-url', default=None, help='LLM base URL override')
@click.option('--llm-api-key-env', default=None, help='Name of env var containing the LLM API key')
@click.option('--llm-required/--llm-fallback', default=False, show_default=True, help='Fail if LLM is unavailable instead of falling back to templates')
@click.option('--llm-temperature', default=0.1, show_default=True, help='LLM temperature')
@click.option('--llm-max-tokens', default=4096, show_default=True, help='LLM max output tokens')
@click.option('--source', type=click.Choice(['auto', 'git', 'filesystem', 'full-scan']), default='auto', show_default=True)
@click.option('--repair', default=2, show_default=True)
@click.option('--pytest', 'pytest_args', default=None, help='Override pytest args')
@click.option('--keep-failing-tests/--rollback-failing-tests', default=False, show_default=True)
@click.option('--partial-rollback/--batch-rollback', default=True, show_default=True, help='Keep passing generated tests and roll back only failing generated tests')
@click.option('--pytest-stream/--no-pytest-stream', default=True, show_default=True, help='Stream pytest output while verification runs')
@click.option('--require-runtime-proof/--no-require-runtime-proof', default=True, show_default=True, help='Rollback generated block if no runtime edge to target is proven after pytest pass')
@click.option('--report/--no-report', default=True, show_default=True, help='Write a static HTML proof report after apply')
@click.option('--open-report', is_flag=True, help='Open the generated HTML report in a browser')
def simple_apply(project, repo_path, base, head, plan_ref, ignore_plan, force_stale_plan, target, source_file, max_targets, strategy, no_llm, llm_provider, llm_model, llm_base_url, llm_api_key_env, llm_required, llm_temperature, llm_max_tokens, source, repair, pytest_args, keep_failing_tests, partial_rollback, pytest_stream, require_runtime_proof, report, open_report):
    """Beginner apply: load a saved plan, patch tests, verify, rollback failures, map runtime."""
    repo_path = repo_path or _repo_path_for_project(project)
    console.print("[cyan]Writes: tests only | Pytest: yes | Runtime map: yes[/cyan]")
    from softgnn_advisor.core.test_generation_agent import TestGenerationAgent
    from softgnn_advisor.core.plan_cache import bundle_to_generation_plans, load_plan_bundle, validate_plan_bundle
    ignored_options = []
    if ignore_plan:
        ignored_options.append('--ignore-plan')
    if target:
        ignored_options.append('--target')
    if source_file:
        ignored_options.append('--file')
    if max_targets != 3:
        ignored_options.append('--max-targets')
    if no_llm:
        ignored_options.append('--no-llm')
    if ignored_options:
        console.print(f"[yellow]Ignored by apply: {', '.join(ignored_options)}. Use `softgnn generate` or `softgnn plan` for generation.[/yellow]")
    llm_required = True if strategy == 'llm' else llm_required
    llm_api_key = os.getenv(llm_api_key_env) if llm_api_key_env else None
    agent = TestGenerationAgent(
        project,
        repo_path=repo_path,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
    )
    try:
        bundle, loaded_path = load_plan_bundle(project, plan_ref)
    except FileNotFoundError:
        console.print(f"[bold red]No saved plan found for project `{project}`.[/bold red]")
        console.print(f"Run [cyan]softgnn plan --project {project}[/cyan] first, or use [cyan]softgnn generate --project {project}[/cyan] for plan+apply.")
        return
    validation = validate_plan_bundle(bundle, repo_path)
    if not validation.valid and not force_stale_plan:
        for warning in validation.warnings:
            console.print(f"[yellow]{warning}[/yellow]")
        console.print("[bold red]Saved plan is stale; apply stopped without generating fresh tests.[/bold red]")
        console.print(f"Run [cyan]softgnn plan --project {project}[/cyan] again, use [cyan]softgnn generate --project {project}[/cyan], or pass [cyan]--force-stale-plan[/cyan].")
        return
    if not validation.valid:
        for warning in validation.warnings:
            console.print(f"[yellow]{warning}[/yellow]")
        console.print("[yellow]Applying stale plan because --force-stale-plan was set.[/yellow]")
    plans = bundle_to_generation_plans(bundle)
    console.print(f"[bold green]Loaded saved plan:[/bold green] {loaded_path}")
    console.print("[cyan]Skipping pre-scan and LLM generation.[/cyan]")
    result = agent.apply_saved_plans(
        plans,
        base=base,
        head=head,
        verify=True,
        repair_iters=repair,
        refresh_runtime=True,
        runtime_mode='per-test',
        confirm_pr_scan=False,
        keep_failing_tests=keep_failing_tests,
        pytest_args=pytest_args,
        generation_strategy=strategy,
        llm_required=llm_required,
        llm_temperature=llm_temperature,
        llm_max_tokens=llm_max_tokens,
        change_source=source,
        partial_rollback=partial_rollback,
        pytest_stream=pytest_stream,
        require_runtime_proof=require_runtime_proof,
    )
    _render_apply_result(result)
    if report:
        from softgnn_advisor.core.report_renderer import build_generate_report_payload
        class _PlanResult:
            pass
        plan_result = _PlanResult()
        plan_result.plans = plans
        payload = build_generate_report_payload(
            project=project,
            plan_result=plan_result,
            apply_result=result,
            repo_path=repo_path,
        )
        _save_and_show_report(project, payload, open_report=open_report)


@cli.command('report')
@click.option('--project', required=True, help='Project name created by setup/prepare')
@click.option('--open', 'open_report', is_flag=True, help='Open latest HTML report in a browser')
def simple_report(project, open_report):
    """Open or print the latest SoftGNN HTML report."""
    from pathlib import Path
    import webbrowser
    from softgnn_advisor.core.report_renderer import latest_report_path

    path = Path(latest_report_path(project))
    if not path.exists():
        console.print(f"[yellow]No report found for project `{project}`.[/yellow]")
        console.print(f"Run [cyan]softgnn generate --project {project}[/cyan] first.")
        return
    console.print(f"[bold green]Latest report:[/bold green] {path}")
    if open_report:
        webbrowser.open(path.resolve().as_uri())


@cli.command('map')
@click.option('--project', required=True, help='Project name created by setup/prepare')
@click.option('--repo-path', default=None, help='Optional override; otherwise read from project metadata')
@click.option('--pytest', 'pytest_args', default='tests', show_default=True)
@click.option('--mode', type=click.Choice(['auto', 'dynamic-context', 'per-test']), default='per-test', show_default=True)
@click.option('--persist/--no-persist', default=True, show_default=True)
@click.option('--max-tests', default=None, type=int)
def simple_map(project, repo_path, pytest_args, mode, persist, max_tests):
    """Beginner map: run pytest runtime coverage mapping."""
    repo_path = repo_path or _repo_path_for_project(project)
    from softgnn_advisor.infrastructure.pipelines.runtime_coverage_mapper import RuntimeCoverageMapper
    mapper = RuntimeCoverageMapper(project, repo_path=repo_path)
    result = mapper.map_runtime_coverage(pytest_args=pytest_args, mode=mode, persist=persist, max_tests=max_tests)
    for warning in result.warnings:
        console.print(f"[yellow]{warning}[/yellow]")
    console.print(f"[bold green]Runtime edges:[/bold green] {len(result.runtime_edges)} | Persisted: {result.persisted}")

@cli.group(name='agent')
def agent_group():
    """Agent-friendly commands for Coding Agents (Antigravity, Claude Code, Codex, Cursor)."""
    pass


@agent_group.command('scan')
@click.option('--project', default=None, help='Project name (defaults to repository folder name)')
@click.option('--path', default='.', help='Path to repository')
@click.option('--base', default='main', show_default=True, help='Base git ref')
@click.option('--head', default='HEAD', show_default=True, help='Head git ref')
@click.option('--source', 'change_source', type=click.Choice(['auto', 'git', 'filesystem', 'full-scan']), default='auto', show_default=True)
@click.option('--lang', default=None, help='Language override (python, typescript, go, etc.)')
@click.option('--json/--no-json', 'as_json', default=True, help='Output as JSON for agent parsing')
def agent_scan(project, path, base, head, change_source, lang, as_json):
    """Scan PR impact and list untested changed functions as structured JSON."""
    import json
    from softgnn_advisor.core.agent_service import AgentService

    svc = AgentService(project=project, repo_path=path, language=lang)
    result = svc.scan(base=base, head=head, change_source=change_source, lang=lang)
    if as_json:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        console.print(f"[bold cyan]Changed files:[/bold cyan] {len(result['changed_files'])}")
        console.print(f"[bold yellow]Missing coverage gaps:[/bold yellow] {len(result['missing_coverage'])}")


@agent_group.command('context')
@click.option('--target', required=True, help='Target function ID, e.g. FUNC:foo')
@click.option('--file', 'source_file', default=None, help='Source file if known')
@click.option('--project', default=None, help='Project name')
@click.option('--path', default='.', help='Path to repository')
@click.option('--lang', default=None, help='Language override')
@click.option('--json/--no-json', 'as_json', default=True, help='Output as JSON')
def agent_context(target, source_file, project, path, lang, as_json):
    """Extract AST code, callers, callees, and test suggestions for a target function."""
    import json
    from softgnn_advisor.core.agent_service import AgentService

    svc = AgentService(project=project, repo_path=path, language=lang)
    result = svc.get_context(target_id=target, source_file=source_file, lang=lang)
    if as_json:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        console.print(f"[bold cyan]Target:[/bold cyan] {result.get('target_id')}")
        console.print(f"[bold green]Signature:[/bold green] {result.get('signature')}")


@agent_group.command('verify-proof')
@click.option('--target', required=True, help='Target function ID, e.g. FUNC:foo')
@click.option('--test', 'test_target', default=None, help='Test file or function, e.g. tests/test_foo.py')
@click.option('--pytest-args', default=None, help='Additional arguments for pytest (Track 1)')
@click.option('--lcov', 'lcov_path', default=None, help='Path to lcov.info or coverage.out (Track 2 Universal)')
@click.option('--test-cmd', default=None, help='Custom test execution command (e.g. npm test -- --coverage)')
@click.option('--lang', default=None, help='Language override')
@click.option('--project', default=None, help='Project name')
@click.option('--path', default='.', help='Path to repository')
@click.option('--json/--no-json', 'as_json', default=True, help='Output as JSON')
def agent_verify_proof(target, test_target, pytest_args, lcov_path, test_cmd, lang, project, path, as_json):
    """Verify runtime execution proof for a written test against the target function."""
    import json
    from softgnn_advisor.core.agent_service import AgentService

    svc = AgentService(project=project, repo_path=path, language=lang)
    result = svc.verify_proof(
        target_id=target,
        test_target=test_target,
        pytest_args=pytest_args,
        lcov_path=lcov_path,
        test_cmd=test_cmd,
        lang=lang,
    )
    if as_json:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        status_color = 'green' if result.get('proof_status') == 'pass' else 'red'
        console.print(f"[{status_color}]{result.get('message')}[/{status_color}]")


@agent_group.command('refresh')
@click.option('--pytest-args', default='tests', show_default=True, help='Pytest target to refresh')
@click.option('--project', default=None, help='Project name')
@click.option('--path', default='.', help='Path to repository')
@click.option('--json/--no-json', 'as_json', default=True, help='Output as JSON')
def agent_refresh(pytest_args, project, path, as_json):
    """Re-run pytest coverage across repository and persist updated runtime edges."""
    import json
    from softgnn_advisor.core.agent_service import AgentService

    svc = AgentService(project=project, repo_path=path)
    result = svc.refresh_runtime(pytest_args=pytest_args)
    if as_json:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        console.print(f"[bold green]Runtime edges count:[/bold green] {result.get('runtime_edges_count')}")


@agent_group.command('impact')
@click.option('--target', required=True, help='Target function or file ID, e.g. FUNC:foo')
@click.option('--mode', type=click.Choice(['hybrid', 'graph', 'gnn']), default='hybrid', show_default=True, help='Impact mode')
@click.option('--threshold', default=0.1, show_default=True, help='Minimum score threshold')
@click.option('--project', default=None, help='Project name')
@click.option('--path', default='.', help='Path to repository')
@click.option('--json/--no-json', 'as_json', default=True, help='Output as JSON')
def agent_impact(target, mode, threshold, project, path, as_json):
    """Query direct dependents and latent HGT blast radius for a target symbol."""
    import json
    from softgnn_advisor.core.agent_service import AgentService

    svc = AgentService(project=project, repo_path=path)
    result = svc.predict_impact(target_symbol=target, mode=mode, threshold=threshold)
    if as_json:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        console.print(f"[bold cyan]Target:[/bold cyan] {result.get('target')}")
        console.print(f"[bold green]Direct Dependents:[/bold green] {len(result.get('direct_dependents', []))}")
        console.print(f"[bold magenta]Latent Risk Candidates:[/bold magenta] {len(result.get('latent_risk_candidates', []))}")


@agent_group.command('triage')
@click.argument('query')
@click.option('--max-devs', default=3, show_default=True, help='Maximum recommended developers')
@click.option('--max-files', default=5, show_default=True, help='Maximum related files')
@click.option('--project', default=None, help='Project name')
@click.option('--path', default='.', help='Path to repository')
@click.option('--json/--no-json', 'as_json', default=True, help='Output as JSON')
def agent_triage(query, max_devs, max_files, project, path, as_json):
    """Recommend best-suited engineers and related files for a bug description or PR."""
    import json
    from softgnn_advisor.core.agent_service import AgentService

    svc = AgentService(project=project, repo_path=path)
    result = svc.triage_bug(query=query, max_devs=max_devs, max_files=max_files)
    if as_json:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        console.print(f"[bold cyan]Query:[/bold cyan] {query}")
        console.print(f"[bold green]Top Engineers:[/bold green] {len(result.get('top_engineers', []))}")
        console.print(f"[bold yellow]Related Files:[/bold yellow] {len(result.get('related_files', []))}")


@agent_group.command('train')
@click.option('--project', default=None, help='Project name')
@click.option('--path', default='.', help='Path to repository')
@click.option('--json/--no-json', 'as_json', default=True, help='Output as JSON')
def agent_train(project, path, as_json):
    """Trigger HGT Graph AI training for the current project."""
    import json
    from softgnn_advisor.core.agent_service import AgentService

    svc = AgentService(project=project, repo_path=path)
    result = svc.train_gnn()
    if as_json:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        status_color = 'green' if result.get('status') == 'success' else 'red'
        console.print(f"[{status_color}]{result.get('message')}[/{status_color}]")



if __name__ == '__main__':
    cli()

