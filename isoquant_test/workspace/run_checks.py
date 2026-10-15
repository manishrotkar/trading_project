"""Compatibility shim: the checks live in scripts/run_checks.py now.

Kept so `python run_checks.py` keeps working.
"""

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent / "scripts" / "run_checks.py"),
               run_name="__main__")
