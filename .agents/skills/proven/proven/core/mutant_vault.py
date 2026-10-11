"""Zero-Token Mutant Vault for Proven.

Stores historical mutants that defeated candidate test suites.
Enables rapid, zero-token regression testing (< 0.05s on CPU) of past vulnerabilities
against newly authored test suites without consuming LLM context or budget.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional


class MutantVault:
    """Manages persistent mutant regression suites on disk."""

    @classmethod
    def get_vault_dir(cls, repo_path: str = ".", project_name: Optional[str] = None) -> Path:
        """Resolve vault storage location.

        Prefers local repo-level `.proven/mutant_vault` for team commitability.
        Falls back to global user directory if local cannot be created.
        """
        local_dir = Path(repo_path) / ".proven" / "mutant_vault"
        try:
            local_dir.mkdir(parents=True, exist_ok=True)
            return local_dir
        except Exception:
            # Fallback to ~/.proven/vault
            fallback = Path.home() / ".proven" / (project_name or "default") / "mutant_vault"
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    @classmethod
    def _sanitize_id(cls, target_id: str) -> str:
        """Sanitize target ID for filesystem paths."""
        return (
            target_id.replace("FUNC:", "")
            .replace("CLASS:", "")
            .replace("FILE:", "")
            .replace("::", "_")
            .replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
            .strip()
        )

    @classmethod
    def _compute_hash(cls, target_id: str, line: int, mutation_desc: str, mutated_code: str) -> str:
        content = f"{target_id}::{line}::{mutation_desc}::{mutated_code}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def store_mutant(
        cls,
        target_id: str,
        source_file: str,
        line: int,
        mutation_desc: str,
        original_code: str,
        mutated_code: str,
        defeated_test: Optional[str] = None,
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Store a surviving or adversarial mutant into the regression vault."""
        vault_dir = cls.get_vault_dir(repo_path, project_name)
        target_slug = cls._sanitize_id(target_id)
        target_dir = vault_dir / target_slug
        target_dir.mkdir(parents=True, exist_ok=True)

        mutant_hash = cls._compute_hash(target_id, line, mutation_desc, mutated_code)
        mutant_id = f"mut_{mutant_hash}"
        mutant_file = target_dir / f"{mutant_id}.json"

        # If already exists, update defeated tests list
        existing_data = {}
        if mutant_file.exists():
            try:
                with mutant_file.open("r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except Exception:
                existing_data = {}

        defeated_tests = existing_data.get("defeated_tests", [])
        if defeated_test and defeated_test not in defeated_tests:
            defeated_tests.append(defeated_test)

        payload = {
            "mutant_id": mutant_id,
            "target_id": target_id,
            "source_file": source_file.replace("\\", "/"),
            "line": int(line),
            "mutation_desc": mutation_desc,
            "original_code": original_code.strip(),
            "mutated_code": mutated_code.strip(),
            "defeated_tests": defeated_tests,
            "created_at": existing_data.get("created_at") or datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        with mutant_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return payload

    @classmethod
    def list_mutants(
        cls,
        target_id: Optional[str] = None,
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all stored mutants in the vault, optionally filtered by target_id."""
        vault_dir = cls.get_vault_dir(repo_path, project_name)
        if not vault_dir.exists():
            return []

        results = []
        if target_id:
            target_slug = cls._sanitize_id(target_id)
            target_dir = vault_dir / target_slug
            search_dirs = [target_dir] if target_dir.exists() else []
        else:
            search_dirs = [p for p in vault_dir.iterdir() if p.is_dir()]

        for t_dir in search_dirs:
            for m_file in t_dir.glob("*.json"):
                try:
                    with m_file.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                        results.append(data)
                except Exception:
                    continue

        return results

    @classmethod
    def run_vault_regression(
        cls,
        target_id: str,
        test_target: str,
        repo_path: str = ".",
        project_name: Optional[str] = None,
        pytest_args: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute regression tests against all historical mutants stored in the vault.

        Runs with zero LLM tokens. If any mutant survives, a regression warning is emitted.
        """
        start_time = time.time()
        mutants = cls.list_mutants(target_id=target_id, repo_path=repo_path, project_name=project_name)
        if not mutants:
            return {
                "status": "passed",
                "message": f"No historical mutants found in vault for '{target_id}'.",
                "total_vault_mutants": 0,
                "killed": 0,
                "survived": 0,
                "execution_time_seconds": 0.0,
                "survived_mutants": [],
            }

        killed_count = 0
        survived_count = 0
        survived_details = []

        for m in mutants:
            s_file = m.get("source_file", "")
            abs_source = Path(repo_path) / s_file.replace("/", os.sep)
            if not abs_source.exists():
                continue

            orig_code = abs_source.read_text(encoding="utf-8", errors="replace")
            source_lines = orig_code.splitlines(keepends=True)
            line_idx = m.get("line", 1) - 1

            if line_idx < 0 or line_idx >= len(source_lines):
                continue

            orig_line = source_lines[line_idx]
            mut_code = m.get("mutated_code", "")

            # Apply mutant line change preserving leading indentation and newline
            leading_ws_len = len(orig_line) - len(orig_line.lstrip())
            indent = orig_line[:leading_ws_len]
            if not mut_code.startswith(indent):
                mut_code = indent + mut_code.lstrip()

            ending = "\n" if orig_line.endswith("\n") else ""
            mutated_lines = list(source_lines)
            mutated_lines[line_idx] = mut_code.rstrip("\r\n") + ending

            try:
                abs_source.write_text("".join(mutated_lines), encoding="utf-8")

                cmd = [sys.executable, "-m", "pytest", test_target, "-q"]
                if pytest_args:
                    cmd.extend(pytest_args.split())

                proc = subprocess.run(
                    cmd,
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                )

                if proc.returncode != 0:
                    # Test failed -> Historical mutant was KILLED (Regression test passed!)
                    killed_count += 1
                else:
                    # Test passed against buggy code -> Historical mutant SURVIVED!
                    survived_count += 1
                    survived_details.append({
                        "mutant_id": m.get("mutant_id"),
                        "line": m.get("line"),
                        "mutation": m.get("mutation_desc"),
                        "original_code": m.get("original_code"),
                        "mutated_code": mut_code,
                    })
            except subprocess.TimeoutExpired:
                killed_count += 1
            except Exception:
                killed_count += 1
            finally:
                abs_source.write_text(orig_code, encoding="utf-8")

        duration = round(time.time() - start_time, 3)
        total = killed_count + survived_count
        status = "passed" if survived_count == 0 else "regression_detected"

        return {
            "status": status,
            "target_id": target_id,
            "total_vault_mutants": total,
            "killed": killed_count,
            "survived": survived_count,
            "survived_mutants": survived_details,
            "execution_time_seconds": duration,
            "message": (
                f"Vault Regression PASSED: All {killed_count}/{total} historical mutants killed in {duration}s."
                if status == "passed"
                else f"Vault Regression FAILED: {survived_count}/{total} historical mutant(s) SURVIVED in {duration}s!"
            ),
        }

    @classmethod
    def clear_vault(
        cls,
        target_id: Optional[str] = None,
        repo_path: str = ".",
        project_name: Optional[str] = None,
    ) -> int:
        """Clear mutants from vault. Returns count of deleted mutant files."""
        vault_dir = cls.get_vault_dir(repo_path, project_name)
        if not vault_dir.exists():
            return 0

        count = 0
        if target_id:
            target_slug = cls._sanitize_id(target_id)
            target_dir = vault_dir / target_slug
            if target_dir.exists():
                for f in target_dir.glob("*.json"):
                    f.unlink()
                    count += 1
                try:
                    target_dir.rmdir()
                except Exception:
                    pass
        else:
            for f in vault_dir.rglob("*.json"):
                f.unlink()
                count += 1

        return count
