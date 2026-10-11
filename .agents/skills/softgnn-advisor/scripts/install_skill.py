#!/usr/bin/env python3
"""Installer script to link or copy the SoftGNN Advisor Skill to Antigravity, Claude Code, or local workspace."""

import argparse
import os
import shutil
import sys
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(description="Install SoftGNN Advisor Skill to AI agent environments")
    parser.add_argument(
        "--target",
        choices=["antigravity", "claude-code", "cursor", "all"],
        default="all",
        help="Target agent environment",
    )
    parser.add_argument(
        "--symlink",
        action="store_true",
        help="Use symlink instead of copying (recommended for active development)",
    )
    args = parser.parse_args()

    skill_source = Path(__file__).resolve().parent.parent
    user_home = Path.home()

    destinations = {}
    if args.target in ("antigravity", "all"):
        destinations["Antigravity"] = user_home / ".gemini" / "config" / "skills" / "softgnn-advisor"
    if args.target in ("claude-code", "all"):
        destinations["Claude Code"] = user_home / ".claude" / "skills" / "softgnn-advisor"
    if args.target in ("cursor", "all"):
        destinations["Cursor / Local (.agents)"] = Path(".agents") / "skills" / "softgnn-advisor"

    print(f"[INSTALL] Installing SoftGNN Advisor Skill from: {skill_source}")

    for name, dest in destinations.items():
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() or dest.is_symlink():
                if dest.is_symlink() or dest.is_file():
                    dest.unlink()
                else:
                    shutil.rmtree(dest)

            if args.symlink:
                try:
                    dest.symlink_to(skill_source, target_is_directory=True)
                    print(f"  [OK] [Symlinked] {name}: {dest}")
                    continue
                except OSError:
                    print(f"  [WARN] Symlink failed (requires admin on Windows). Falling back to copy...")

            shutil.copytree(skill_source, dest)
            print(f"  [OK] [Copied] {name}: {dest}")
        except Exception as e:
            print(f"  [ERROR] Failed to install for {name}: {e}")

    print("\n[SUCCESS] Installation complete! Coding Agents will now detect the 'softgnn-advisor' skill automatically.")


if __name__ == "__main__":
    main()
