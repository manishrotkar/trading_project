"""Command-line front-end for todoapp.

Exit codes: 0 success, 1 unknown task id, 2 bad usage or blank title.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import core, storage

EXIT_OK = 0
EXIT_MISSING = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="todoapp",
        description="A tiny command-line to-do application.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="data file to use instead of the default (data/tasks.json)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="add a task")
    p_add.add_argument("title", nargs="+", help="task title (one or more words)")

    sub.add_parser("list", help="show all tasks")

    p_done = sub.add_parser("done", help="mark a task complete")
    p_done.add_argument("id", type=int, help="task id")

    p_rm = sub.add_parser("remove", help="remove a task")
    p_rm.add_argument("id", type=int, help="task id")

    return parser


def _print_list(tasks: list[dict]) -> None:
    if not tasks:
        print("(no tasks)")
        return
    for task in core.list_tasks(tasks):
        mark = "x" if task["done"] else " "
        print(f"[{mark}] {task['id']}. {task['title']}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    path = args.file if args.file is not None else storage.DEFAULT_DATA_FILE
    tasks = storage.load_tasks(path)

    try:
        if args.command == "add":
            task = core.add_task(tasks, " ".join(args.title))
            storage.save_tasks(tasks, path)
            print(f"Added #{task['id']}: {task['title']}")
        elif args.command == "list":
            _print_list(tasks)
        elif args.command == "done":
            task = core.complete_task(tasks, args.id)
            if task is None:
                print(f"Error: no task with id {args.id}", file=sys.stderr)
                return EXIT_MISSING
            storage.save_tasks(tasks, path)
        elif args.command == "remove":
            if not core.remove_task(tasks, args.id):
                print(f"Error: no task with id {args.id}", file=sys.stderr)
                return EXIT_MISSING
            storage.save_tasks(tasks, path)
    except ValueError as exc:  # blank title
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
