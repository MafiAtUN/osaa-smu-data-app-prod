"""Backward-compatible entry point — delegates to app/main.py.

Usage:
    streamlit run app.py
    streamlit run app/main.py   (preferred)
"""

from pathlib import Path

exec(compile(Path("app/main.py").read_text(), "app/main.py", "exec"))
