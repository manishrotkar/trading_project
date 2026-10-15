"""Tests for the todoapp command-line interface."""

import json
from pathlib import Path

import pytest

from todoapp import cli


@pytest.fixture()
def data_file(tmp_path):
    return tmp_path / "tasks.json"


def run_cli(argv, data_file, capsys):
    """Run the CLI once and return its exit code."""
    code = cli.main(["--file", str(data_file), *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_add_then_list(data_file, capsys):
    code, out, _ = run_cli(["add", "buy milk"], data_file, capsys)
    assert code == 0
    assert "Added #1" in out

    code, out, _ = run_cli(["list"], data_file, capsys)
    assert code == 0
    assert "[ ] 1. buy milk" in out


def test_done_marks_task_complete(data_file, capsys):
    run_cli(["add", "buy milk"], data_file, capsys)
    code, out, _ = run_cli(["done", "1"], data_file, capsys)
    assert code == 0

    code, out, _ = run_cli(["list"], data_file, capsys)
    assert code == 0
    assert "[x] 1. buy milk" in out


def test_done_unknown_id_fails(data_file, capsys):
    code, _, err = run_cli(["done", "7"], data_file, capsys)
    assert code == 1
    assert "no task with id 7" in err


def test_remove_deletes_task(data_file, capsys):
    run_cli(["add", "buy milk"], data_file, capsys)
    code, _, _ = run_cli(["remove", "1"], data_file, capsys)
    assert code == 0

    code, out, _ = run_cli(["list"], data_file, capsys)
    assert code == 0
    assert "(no tasks)" in out


def test_remove_unknown_id_fails(data_file, capsys):
    code, _, err = run_cli(["remove", "9"], data_file, capsys)
    assert code == 1
    assert "no task with id 9" in err


def test_blank_title_fails(data_file, capsys):
    code, _, err = run_cli(["add", "   "], data_file, capsys)
    assert code == 2
    assert "must not be empty" in err


def test_data_is_persisted_as_json(data_file, capsys):
    run_cli(["add", "buy milk"], data_file, capsys)
    data = json.loads(data_file.read_text(encoding="utf-8"))
    assert data == [{"id": 1, "title": "buy milk", "done": False}]


def test_help_exits_with_usage_error(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--help"])
    assert excinfo.value.code == 0


def test_no_subcommand_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2
