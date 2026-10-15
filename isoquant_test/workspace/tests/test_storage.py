"""Unit tests for todo.storage.

These tests use a temporary directory so they never touch the real
data/tasks.json file.
"""

import json
import tempfile
import unittest
from pathlib import Path

from todo import storage


class StorageTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "tasks.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_load_missing_file_returns_empty_list(self):
        self.assertEqual(storage.load_tasks(self.path), [])

    def test_load_empty_file_returns_empty_list(self):
        self.path.write_text("", encoding="utf-8")
        self.assertEqual(storage.load_tasks(self.path), [])

    def test_save_and_load_round_trip(self):
        tasks = [{"id": 1, "title": "Buy milk", "done": False}]
        storage.save_tasks(tasks, self.path)
        self.assertEqual(storage.load_tasks(self.path), tasks)

    def test_save_creates_parent_directories(self):
        deep_path = Path(self._tmp.name) / "a" / "b" / "tasks.json"
        storage.save_tasks([], deep_path)
        self.assertTrue(deep_path.exists())

    def test_save_writes_valid_json(self):
        tasks = [{"id": 1, "title": "Write tests", "done": True}]
        storage.save_tasks(tasks, self.path)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), tasks)

    def test_load_malformed_json_raises(self):
        self.path.write_text("{not valid json", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            storage.load_tasks(self.path)


if __name__ == "__main__":
    unittest.main()
