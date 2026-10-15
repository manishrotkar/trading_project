"""Tests for the command-line interface."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "textstats.cli", *argv],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )


def test_cli_text_output(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("Hello world\nHello again", encoding="utf-8")

    result = run_cli(str(sample))
    lines = result.stdout.splitlines()
    assert len(lines) == 6
    assert lines[0].startswith("lines") and lines[0].endswith(": 2")
    assert lines[1].startswith("words") and lines[1].endswith(": 4")
    assert lines[4].startswith("top_word") and lines[4].endswith(": hello")
    # every row uses the same aligned column width
    positions = [line.index(":") for line in lines]
    assert positions == [positions[0]] * 6


def test_cli_json_output(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("a a b", encoding="utf-8")

    result = run_cli(str(sample), "--json")
    data = json.loads(result.stdout)
    assert data["words"] == 3
    assert data["top_word"] == "a"
    assert data["top_word_count"] == 2


def test_cli_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope.txt"
    proc = subprocess.run(
        [sys.executable, "-m", "textstats.cli", str(missing)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode != 0
    assert "nope.txt" in proc.stderr
