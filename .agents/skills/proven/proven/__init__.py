"""Proven — graph-guided, runtime-proven, LLM-assisted PR test quality gate."""
import sys

# Ensure UTF-8 output streams on Windows to prevent charmap/cp1252 crashes
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

__version__ = "1.0.0"
