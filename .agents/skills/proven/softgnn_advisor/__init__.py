"""Backward-compatibility shim for softgnn_advisor.

Redirects all imports of softgnn_advisor and its submodules to proven.
"""

import sys
import importlib

# Ensure UTF-8 output streams on Windows
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

# Import proven and register redirect hook
import proven
from importlib.machinery import ModuleSpec


class _RedirectLoader:
    def __init__(self, mod):
        self.mod = mod

    def create_module(self, spec):
        return self.mod

    def exec_module(self, module):
        pass


class _SoftgnnRedirectFinder:
    def find_spec(self, fullname, path, target=None):
        if fullname == "softgnn_advisor" or fullname.startswith("softgnn_advisor."):
            proven_name = fullname.replace("softgnn_advisor", "proven", 1)
            try:
                mod = importlib.import_module(proven_name)
                return ModuleSpec(fullname, _RedirectLoader(mod), origin=getattr(mod, "__file__", None))
            except Exception:
                return None
        return None


sys.meta_path.insert(0, _SoftgnnRedirectFinder())

__version__ = proven.__version__
