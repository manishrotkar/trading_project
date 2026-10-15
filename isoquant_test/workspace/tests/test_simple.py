"""A simple smoke test to verify the test suite runs."""

import unittest

from todo import core


class SimpleTest(unittest.TestCase):
    def test_new_task_is_not_done(self):
        tasks = []
        task = core.add_task(tasks, "hello world")
        self.assertEqual(task["title"], "hello world")
        self.assertFalse(task["done"])

    def test_list_tasks_sorts_by_id(self):
        tasks = [{"id": 2, "title": "b", "done": False},
                 {"id": 1, "title": "a", "done": True}]
        self.assertEqual([t["id"] for t in core.list_tasks(tasks)], [1, 2])


if __name__ == "__main__":
    unittest.main()
