"""Print a `tree`-style listing of the workspace.

Cache/build directories (__pycache__, .pytest_cache, .git, ...) are skipped.
Usage:  python print_tree.py [root] [--max-depth N]
"""

import argparse
import sys
from pathlib import Path

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", ".mypy_cache", ".venv", "venv"}


def walk(dir_path: Path, prefix: str, lines: list, max_depth: int, depth: int):
    if max_depth is not None and depth > max_depth:
        return

    entries = sorted(
        dir_path.iterdir(),
        key=lambda p: (p.is_file(), p.name.lower()),  # dirs first, then files
    )
    # drop skipped dirs from the display
    entries = [e for e in entries if not (e.is_dir() and e.name in SKIP_DIRS)]

    for i, entry in enumerate(entries):
        last = i == len(entries) - 1
        connector = "└── " if last else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if last else "│   "
            walk(entry, prefix + extension, lines, max_depth, depth + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="directory to list")
    parser.add_argument("--max-depth", type=int, default=None)
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"Error: '{root}' is not a directory.", file=sys.stderr)
        return 2

    lines = [str(root)]
    walk(root, "", lines, args.max_depth, 1)
    print("\n".join(lines))
    print(f"\n{len(lines) - 1} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
