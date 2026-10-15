"""Command-line entry point for textstats."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import analyze


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="textstats",
        description="Print basic statistics about a text file.",
    )
    parser.add_argument("path", type=Path, help="path to a UTF-8 text file")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="print the result as JSON instead of text",
    )
    args = parser.parse_args(argv)

    try:
        text = args.path.read_text(encoding="utf-8")
    except FileNotFoundError:
        parser.error(f"file not found: {args.path}")
    except UnicodeDecodeError:
        parser.error(f"file is not valid UTF-8: {args.path}")

    stats = analyze(text)

    if args.as_json:
        print(json.dumps(stats, indent=2))
    else:
        width = max(len(k) for k in stats)
        for key, value in stats.items():
            print(f"{key:<{width}} : {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
