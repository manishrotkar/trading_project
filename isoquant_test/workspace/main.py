"""Command-line interface for the to-do app.

Usage:
    python main.py add "Buy milk"
    python main.py add --priority high "Buy milk"
    python main.py list
    python main.py list --order priority
    python main.py list --done
    python main.py list --priority high
    python main.py done 1
    python main.py remove 1
"""

import argparse
import sys

from todo import core, storage


def _priority(value):
    """argparse type: validate a --priority value."""
    value = value.strip().lower()
    if value not in core.VALID_PRIORITIES:
        raise argparse.ArgumentTypeError(
            f"invalid priority {value!r} "
            f"(choose from: {', '.join(core.PRIORITY_ORDER)})"
        )
    return value


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="A minimal command-line to-do app.",
    )
    sub = parser.add_subparsers(dest="command")

    add = sub.add_parser("add", help="add a task")
    add.add_argument("title", nargs="+", help="the task title")
    add.add_argument(
        "-p",
        "--priority",
        type=_priority,
        default=core.DEFAULT_PRIORITY,
        help="task priority: %(choices)s (default: %(default)s)",
    )

    list_cmd = sub.add_parser("list", help="show tasks")
    list_cmd.add_argument(
        "--order",
        choices=["id", "priority", "status"],
        default="id",
        help="sort order (default: id)",
    )
    status = list_cmd.add_mutually_exclusive_group()
    status.add_argument(
        "--done",
        dest="done",
        action="store_true",
        help="show only completed tasks",
    )
    status.add_argument(
        "--pending",
        dest="done",
        action="store_false",
        help="show only pending tasks",
    )
    list_cmd.add_argument(
        "--priority",
        type=_priority,
        default=None,
        help="show only tasks with this priority",
    )

    for name, help_text in (("done", "mark a task complete"), ("remove", "delete a task")):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("id", type=int, help="the task id")

    return parser


def format_task(task):
    """Return a one-line human-readable representation of a task."""
    marker = "x" if task["done"] else " "
    return f"[{marker}] {task['id']}. {task['title']}"


def format_task_with_priority(task):
    """Format a task including its priority tag (omitted for the default)."""
    priority = core.get_priority(task)
    line = format_task(task)
    if priority != core.DEFAULT_PRIORITY:
        line += f" ({priority})"
    return line


def main(argv=None):
    """Run one CLI command. Returns a process exit code."""
    argv = list(sys.argv if argv is None else argv)
    parser = _build_parser()
    args = parser.parse_args(argv[1:])

    tasks = storage.load_tasks()

    if args.command == "add":
        task = core.add_task(tasks, " ".join(args.title), priority=args.priority)
        storage.save_tasks(tasks)
        print(f"Added: {format_task_with_priority(task)}")
        return 0

    if args.command == "list":
        shown = core.filter_tasks(
            core.list_tasks(tasks),
            priority=args.priority,
            done=args.done,
        )
        if not shown:
            order = " ".join(argv[2:])
            print(
                f"No matching tasks ({order}). "
                'Try: python main.py add "Something"'
            )
        for task in shown:
            print(format_task_with_priority(task))
        return 0

    if args.command == "done":
        task = core.complete_task(tasks, args.id)
        if task is None:
            print(f"Error: no task with id {args.id}.", file=sys.stderr)
            return 1
        storage.save_tasks(tasks)
        print(f"Completed: {format_task_with_priority(task)}")
        return 0

    if args.command == "remove":
        if not core.remove_task(tasks, args.id):
            print(f"Error: no task with id {args.id}.", file=sys.stderr)
            return 1
        storage.save_tasks(tasks)
        print(f"Removed task {args.id}.")
        return 0

    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
