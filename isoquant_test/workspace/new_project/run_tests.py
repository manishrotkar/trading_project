"""Run the pytest suite for the new project."""

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent
sys.exit(pytest.main(["-v", str(PROJECT / "tests")]))
