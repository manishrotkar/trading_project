"""Unit tests for todo.core."""

import unittest

from todo import core


class CoreTest(unittest.TestCase):
    def test_add_task_assigns_incrementing_ids(self):
        tasks = []
        core.add_task(tasks, "first")
        core.add_task(tasks, "second")
        self.assertEqual([t["id"] for t in tasks], [1, 2])

    def test_add_task_rejects_blank_title(self):
        with self.assertRaises(ValueError):
            core.add_task([], "   ")

    def test_complete_task(self):
        tasks = []
        task = core.add_task(tasks, "write tests")
        self.assertTrue(core.complete_task(tasks, task["id"])["done"])
        self.assertFalse(core.complete_task(tasks, 999))

    def test_remove_task(self):
        tasks = []
        task = core.add_task(tasks, "temp")
        self.assertTrue(core.remove_task(tasks, task["id"]))
        self.assertFalse(tasks)
        self.assertFalse(core.remove_task(tasks, task["id"]))


class PriorityTest(unittest.TestCase):
    def test_default_priority_is_medium(self):
        self.assertEqual(core.DEFAULT_PRIORITY, "medium")

    def test_add_task_without_priority_omits_the_key(self):
        tasks = []
        task = core.add_task(tasks, "plain")
        self.assertNotIn("priority", task)
        self.assertEqual(core.get_priority(task), "medium")

    def test_add_task_with_priority(self):
        tasks = []
        task = core.add_task(tasks, "urgent", priority="high")
        self.assertEqual(task["priority"], "high")
        self.assertEqual(core.get_priority(task), "high")

    def test_add_task_normalizes_casing(self):
        tasks = []
        task = core.add_task(tasks, "quick", priority="  LOW ")
        self.assertEqual(task["priority"], "low")

    def test_add_task_rejects_invalid_priority(self):
        with self.assertRaises(ValueError):
            core.add_task([], "oops", priority="urgent")
        with self.assertRaises(ValueError):
            core.add_task([], "oops", priority=5)

    def test_get_priority_handles_missing_or_bad_value(self):
        self.assertEqual(core.get_priority({}), "medium")
        self.assertEqual(core.get_priority({"priority": None}), "medium")
        self.assertEqual(core.get_priority({"priority": "HIGH"}), "high")

    def test_list_tasks_by_priority_puts_high_first(self):
        tasks = [
            {"id": 1, "title": "low", "done": False, "priority": "low"},
            {"id": 2, "title": "high", "done": False, "priority": "high"},
            {"id": 3, "title": "default", "done": False},
        ]
        ordered = core.list_tasks(tasks, order="priority")
        self.assertEqual([t["id"] for t in ordered], [2, 3, 1])

    def test_list_tasks_by_priority_keeps_done_last(self):
        tasks = [
            {"id": 1, "title": "done-high", "done": True, "priority": "high"},
            {"id": 2, "title": "pending-low", "done": False, "priority": "low"},
        ]
        ordered = core.list_tasks(tasks, order="priority")
        self.assertEqual([t["id"] for t in ordered], [2, 1])

    def test_list_tasks_by_status(self):
        tasks = [
            {"id": 1, "title": "done", "done": True},
            {"id": 2, "title": "pending", "done": False},
        ]
        ordered = core.list_tasks(tasks, order="status")
        self.assertEqual([t["id"] for t in ordered], [2, 1])
        # default order is unchanged
        self.assertEqual([t["id"] for t in core.list_tasks(tasks)], [1, 2])

    def test_filter_tasks_by_priority(self):
        tasks = [
            {"id": 1, "title": "high", "done": False, "priority": "high"},
            {"id": 2, "title": "default", "done": False},
        ]
        self.assertEqual(
            [t["id"] for t in core.filter_tasks(tasks, priority="high")], [1]
        )
        self.assertEqual(
            [t["id"] for t in core.filter_tasks(tasks, priority="medium")], [2]
        )

    def test_filter_tasks_rejects_unknown_priority(self):
        with self.assertRaises(ValueError):
            core.filter_tasks(
                [{"id": 1, "title": "x", "done": False}], priority="urgent"
            )

    def test_filter_tasks_by_done(self):
        tasks = [
            {"id": 1, "title": "done", "done": True},
            {"id": 2, "title": "pending", "done": False},
        ]
        self.assertEqual([t["id"] for t in core.filter_tasks(tasks, done=True)], [1])
        self.assertEqual([t["id"] for t in core.filter_tasks(tasks, done=False)], [2])

    def test_filter_tasks_combines_filters(self):
        tasks = [
            {"id": 1, "title": "high-done", "done": True, "priority": "high"},
            {"id": 2, "title": "high-pending", "done": False, "priority": "high"},
            {"id": 3, "title": "pending", "done": False},
        ]
        matched = core.filter_tasks(tasks, priority="high", done=False)
        self.assertEqual([t["id"] for t in matched], [2])


if __name__ == "__main__":
    unittest.main()
