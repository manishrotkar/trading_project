"""Unit tests for todoapp.storage."""

import json

import pytest

from todoapp.storage import load_tasks, save_tasks


def test_missing_file_returns_empty_list(tmp_path):
    assert load_tasks(tmp_path / "absent.json") == []


def test_empty_file_returns_empty_list(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("")
    assert load_tasks(path) == []


def test_save_load_round_trip(tmp_path):
    path = tmp_path / "tasks.json"
    tasks = [{"id": 1, "title": "buy milk", "done": False}]
    save_tasks(tasks, path)
    assert load_tasks(path) == tasks


def test_save_creates_parent_directories(tmp_path):
    path = tmp_path / "deep" / "nested" / "tasks.json"
    save_tasks([], path)
    assert path.exists()


def test_saved_file_is_valid_json(tmp_path):
    path = tmp_path / "tasks.json"
    save_tasks([{"id": 1, "title": "x", "done": True}], path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[0]["done"] is True


def test_malformed_json_raises(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json")
    with pytest.raises(json.JSONDecodeError):
        load_tasks(path)
