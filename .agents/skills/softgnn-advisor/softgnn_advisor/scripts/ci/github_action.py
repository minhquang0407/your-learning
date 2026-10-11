"""SoftGNN Advisor — GitHub Action PR Quality Gate runner.

Inspects PR changes, detects missing runtime test coverage,
posts or updates a PR comment in-place (anti-spam),
writes to GITHUB_STEP_SUMMARY, and enforces the quality gate.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

# Force UTF-8 on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

COMMENT_MARKER = "<!-- softgnn-audit-comment -->"


def parse_event_payload(event_path: Optional[str]) -> Dict[str, Any]:
    """Parse GitHub Action event payload JSON."""
    if not event_path or not os.path.exists(event_path):
        return {}
    try:
        with open(event_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        sys.stderr.write(f"[SoftGNN] Warning: Failed to parse GITHUB_EVENT_PATH: {exc}\n")
        return {}


def format_audit_markdown(scan_result: Dict[str, Any], repo_full_name: str = "") -> str:
    """Generate Markdown audit report suitable for PR comments and Step Summary."""
    missing_targets: List[Dict[str, Any]] = scan_result.get("missing_coverage", [])
    changed_count: int = scan_result.get("changed_count", 0)
    contract_diff_count: int = scan_result.get("contract_diff_count", 0)
    missing_count: int = len(missing_targets)
    lang: str = scan_result.get("language", "unknown")

    contract_status = "Warning (> 0)" if contract_diff_count > 0 else "OK"

    lines = [COMMENT_MARKER]

    if missing_count > 0:
        lines.append("## SoftGNN Advisor — Untested Changes Detected\n")
        lines.append(
            "> SoftGNN scanned this PR and identified changed functions that lack dynamic runtime execution proof.\n"
        )
        lines.append("### Quality Audit Overview")
        lines.append("| Metric | Value | Status |")
        lines.append("|---|---|---|")
        lines.append(f"| **Total Changed Functions** | `{changed_count}` | Analyzed |")
        lines.append(f"| **Contract / Interface Changes** | `{contract_diff_count}` | {contract_status} |")
        lines.append(f"| **Missing Runtime Proof** | **`{missing_count}`** | **Needs Action** |")
        lines.append(f"| **Detected Language** | `{lang}` | Track Mode |\n")

        lines.append("### Functions Requiring Test Coverage")
        lines.append("| Target Function | Source File | Risk Score | Recommendation |")
        lines.append("|---|---|---|---|")
        for target in missing_targets:
            tid = target.get("target_id", "UNKNOWN")
            sfile = target.get("file", "unknown")
            rscore = target.get("risk", 0.5)
            lines.append(f"| `{tid}` | `{sfile}` | `{rscore:.2f}` | Needs test with Runtime Proof |")
        lines.append("")

        first_tid = missing_targets[0].get("target_id", "")
        lines.append("---")
        lines.append("### Coding Agent Guidance (Antigravity / Claude Code / Codex / Copilot)")
        lines.append("To author tests for target functions and achieve Titanium Proof:")
        lines.append("```bash")
        lines.append(f"# 1. Extract function AST context and contracts:")
        lines.append(f'python skills/softgnn-advisor/scripts/get_target_context.py --target "{first_tid}"')
        lines.append("")
        lines.append(f"# 2. Verify runtime proof after authoring test:")
        lines.append(f'python skills/softgnn-advisor/scripts/verify_runtime_proof.py --target "{first_tid}" --test "path/to/test" --mutation-check')
        lines.append("```")
    else:
        lines.append("## SoftGNN Advisor — All Changed Functions Have Runtime Proof!\n")
        lines.append(
            "> SoftGNN PR impact scan verified: 100% of changed logic is executed by runtime tests.\n"
        )
        lines.append("### Quality Audit Overview")
        lines.append("| Metric | Value | Status |")
        lines.append("|---|---|---|")
        lines.append(f"| **Total Changed Functions** | `{changed_count}` | Analyzed |")
        lines.append(f"| **Contract / Interface Changes** | `{contract_diff_count}` | {contract_status} |")
        lines.append(f"| **Functions with Runtime Proof** | **`{changed_count}/{changed_count} (100%)`** | **Passed** |")
        lines.append(f"| **Detected Language** | `{lang}` | Track Mode |\n")
        lines.append("**All changes are verified with runtime proof and safe for review.**")

    return "\n".join(lines) + "\n"


def github_api_request(url: str, token: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Any:
    """Execute a GitHub REST API request with standard headers."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "softgnn-advisor-action",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode("utf-8")
        if content:
            return json.loads(content)
        return {}


def update_or_create_comment(repo_full_name: str, pr_number: int, token: str, markdown_body: str) -> None:
    """Find existing SoftGNN comment by marker and update in-place, or create new."""
    list_url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
    try:
        comments = github_api_request(list_url, token, method="GET")
    except Exception as exc:
        sys.stderr.write(f"[SoftGNN] Error fetching PR comments: {exc}\n")
        return

    existing_comment_id = None
    if isinstance(comments, list):
        for c in comments:
            if COMMENT_MARKER in c.get("body", ""):
                existing_comment_id = c.get("id")
                break

    if existing_comment_id:
        update_url = f"https://api.github.com/repos/{repo_full_name}/issues/comments/{existing_comment_id}"
        try:
            github_api_request(update_url, token, method="PATCH", data={"body": markdown_body})
            print(f"[SoftGNN] Updated existing PR comment #{existing_comment_id} on {repo_full_name}#{pr_number}")
        except Exception as exc:
            sys.stderr.write(f"[SoftGNN] Error updating comment #{existing_comment_id}: {exc}\n")
    else:
        try:
            github_api_request(list_url, token, method="POST", data={"body": markdown_body})
            print(f"[SoftGNN] Created new PR comment on {repo_full_name}#{pr_number}")
        except Exception as exc:
            sys.stderr.write(f"[SoftGNN] Error creating PR comment: {exc}\n")


def write_step_summary(summary_path: Optional[str], markdown_content: str) -> None:
    """Write markdown audit report to GITHUB_STEP_SUMMARY."""
    if not summary_path:
        return
    try:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(markdown_content + "\n")
        print(f"[SoftGNN] Written report to Step Summary: {summary_path}")
    except Exception as exc:
        sys.stderr.write(f"[SoftGNN] Warning: Failed to write to GITHUB_STEP_SUMMARY: {exc}\n")


def write_github_outputs(output_path: Optional[str], outputs: Dict[str, Any]) -> None:
    """Write key-value pairs to GITHUB_OUTPUT."""
    if not output_path:
        return
    try:
        with open(output_path, "a", encoding="utf-8") as f:
            for k, v in outputs.items():
                f.write(f"{k}={v}\n")
    except Exception as exc:
        sys.stderr.write(f"[SoftGNN] Warning: Failed to write to GITHUB_OUTPUT: {exc}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="SoftGNN Advisor GitHub Action Runner")
    parser.add_argument("--github-token", default=os.getenv("GITHUB_TOKEN") or os.getenv("INPUT_GITHUB_TOKEN", ""))
    parser.add_argument("--base", default=os.getenv("BASE_REF") or os.getenv("INPUT_BASE", ""))
    parser.add_argument("--head", default=os.getenv("HEAD_REF") or os.getenv("INPUT_HEAD", ""))
    parser.add_argument("--fail-on-missing", default=os.getenv("INPUT_FAIL_ON_MISSING", "false"))
    parser.add_argument("--comment-pr", default=os.getenv("INPUT_COMMENT_PR", "true"))
    parser.add_argument("--lang", default=os.getenv("INPUT_LANG", "auto"))
    parser.add_argument("--repo-path", default=".")
    parser.add_argument("--event-path", default=os.getenv("GITHUB_EVENT_PATH"))
    parser.add_argument("--step-summary", default=os.getenv("GITHUB_STEP_SUMMARY"))
    parser.add_argument("--github-output", default=os.getenv("GITHUB_OUTPUT"))
    args = parser.parse_args()

    event = parse_event_payload(args.event_path)
    pr_data = event.get("pull_request")
    repo_data = event.get("repository", {})

    repo_full_name = repo_data.get("full_name") or os.getenv("GITHUB_REPOSITORY", "")
    pr_number = pr_data.get("number") if pr_data else None

    # Derive base and head commits
    base_ref = args.base
    head_ref = args.head

    if not base_ref and pr_data:
        base_ref = pr_data.get("base", {}).get("sha", "")
    if not head_ref and pr_data:
        head_ref = pr_data.get("head", {}).get("sha", "")

    if not base_ref:
        base_ref = "main"
    if not head_ref:
        head_ref = "HEAD"

    print(f"[SoftGNN] Running audit on repository: {repo_full_name or args.repo_path}")
    print(f"[SoftGNN] Comparing range: {base_ref}...{head_ref} (lang={args.lang})")

    from softgnn_advisor.core.agent_service import AgentService

    try:
        service = AgentService(repo_path=args.repo_path)
        scan_result = service.scan(base_ref=base_ref, head_ref=head_ref, lang=args.lang)
    except Exception as exc:
        sys.stderr.write(f"[SoftGNN] Error during impact scan: {exc}\n")
        sys.exit(1)

    missing_count = len(scan_result.get("missing_coverage", []))
    changed_count = scan_result.get("changed_count", 0)
    has_gaps = "true" if missing_count > 0 else "false"

    markdown_report = format_audit_markdown(scan_result, repo_full_name=repo_full_name)

    # 1. Write to Step Summary
    write_step_summary(args.step_summary, markdown_report)

    # 2. Write Action Outputs
    write_github_outputs(args.github_output, {
        "missing-count": missing_count,
        "changed-count": changed_count,
        "has-gaps": has_gaps,
    })

    # 3. Comment on PR
    should_comment = args.comment_pr.lower() in ("true", "1", "yes")
    if should_comment and pr_number and repo_full_name and args.github_token:
        update_or_create_comment(repo_full_name, pr_number, args.github_token, markdown_report)
    elif should_comment and not pr_number:
        print("[SoftGNN] Notice: Not a pull_request event, skipping PR comment.")

    # 4. Strict Quality Gate check
    fail_on_missing = args.fail_on_missing.lower() in ("true", "1", "yes")
    if fail_on_missing and missing_count > 0:
        print(f"\n[SoftGNN Quality Gate] FAILED: {missing_count} functions are missing runtime test proof.")
        sys.exit(1)
    else:
        print(f"\n[SoftGNN Quality Gate] PASSED: Quality gate criteria met.")
        sys.exit(0)


if __name__ == "__main__":
    main()
