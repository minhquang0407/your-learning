"""Framework-neutral application boundary for Your Learning.

TODO:
- Keep this package independent from Streamlit, FastAPI, and database SDKs.
- Expose use-case services through ``LearningApplication`` only.
- Move orchestration out of ``main.py`` incrementally; do not rewrite everything at once.
"""

from application.facade import LearningApplication

__all__ = ["LearningApplication"]
