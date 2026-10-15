# Tiny To-Do

A minimal command-line to-do app written in pure Python — **the application
code is standard library only**. External dependencies are for development
and testing only, and are declared in `requirements.in` (source) and
`requirements.txt` (pinned lock file).

Tasks are stored as a simple JSON list, so the data is easy to inspect, back
up, and version by hand.

## Requirements

- Python 3.10+ (the app itself needs no third-party packages)

## Dependencies

Runtime dependencies of the app: **none** — `main.py` and the `todo/`
package use only the standard library (`json`, `pathlib`, `os`, `sys`).

Development dependencies (documented in `requirements.in`):

| Package  | Version   | Why it is needed |
|----------|-----------|------------------|
| `pytest` | `>= 8.0`  | Runs the unit tests in `tests/` and the smoke test in `scripts/run_checks.py`. pytest 9.x requires Python ≥ 3.10. |
| `tomli`  | `>= 1.1.0` | Backport of the stdlib `tomllib`, needed on Python < 3.11 if any TOML config is parsed; a no-op on 3.11+, where the stdlib module is used instead. |

### The two dependency files

- **`requirements.in`** — the hand-maintained list of *direct* dependencies
  with the loose ranges developers actually need. Edit this when you add or
  upgrade a dependency.
- **`requirements.txt`** — the generated lock file: every package pinned to
  the exact version tested against, including pytest's own transitive
  dependencies (`iniconfig`, `packaging`, `pluggy`, `pygments`). Regenerate
  it with [pip-tools](https://pip-tools.github.io/) after changing the
  `.in` file:

  ```bash
  pip install pip-tools
  pip-compile requirements.in   # regenerates requirements.txt
  ```

Install the pinned environment with:

```bash
pip install -r requirements.txt
```

Notes:

- The lock file is pinned against Python 3.13, the version used for
  development; `pip-compile` re-resolves the same `.in` file for any other
  interpreter.
- Platform-specific markers (`sys_platform == "win32"` for `colorama`,
  `python_version < "3.11"` for `tomli`/`exceptiongroup`) mean most
  environments install fewer packages than the lock file lists.

## Usage

Every invocation runs one command and exits:

```bash
python main.py add "Buy milk"                     # add a task (medium priority)
python main.py add --priority high "Write report" # add an important task
python main.py add -p low "Tidy the folder"       # --priority also has a short form
python main.py list                               # show all tasks
python main.py list --order priority              # pending first, high priority first
python main.py list --order status                # pending first (by id), done last
python main.py list --pending                     # hide completed tasks
python main.py list --done                        # show only completed tasks
python main.py list --priority high               # only tasks tagged high
python main.py list --priority low --pending      # filters combine
python main.py done 1                             # mark task 1 as complete
python main.py remove 2                           # delete task 2
```

Running `python main.py --help` prints full usage; running it with no
arguments prints usage and exits with code `2`.

Example output:

```
$ python main.py list
[ ] 1. Buy milk
[ ] 2. Write report (high)
[ ] 3. Tidy the folder (low)
$ python main.py list --order priority
[ ] 2. Write report (high)
[ ] 1. Buy milk
[ ] 3. Tidy the folder (low)
```

- `[x]` marks a completed task, `[ ]` a pending one.
- Task ids are stable and never reused; `done` and `remove` both take an id.
- Multi-word titles work without extra quoting: `python main.py add buy milk`.
- A task's priority tag is shown after the title unless it is the default
  (`medium`) — untitled-priority tasks look exactly as they always did.

### Priorities

Every task has one of three priorities: **high**, **medium** (the default)
or **low**. The value is case-insensitive on input and stored lowercase.

- `add --priority high` sets it explicitly; anything omitted is `medium`.
- An unknown priority (e.g. `--priority urgent`) is rejected with a
  clear error and exit code `2`.
- `--order priority` shows pending tasks first, high priority first, and
  moves completed tasks to the bottom regardless of their priority.
- `--priority NAME` filters; combine it with `--done` / `--pending`.
- Tasks are stored as `{"id": 1, "title": "Buy milk", "done": false}` with
  an optional `"priority"` key — older `data/tasks.json` files without it
  keep working unchanged.

### Exit codes and error handling

| Situation                                    | Behaviour                                  | Exit code |
|----------------------------------------------|--------------------------------------------|-----------|
| Success                                       | Command runs, result printed              | `0`       |
| Task id given to `done`/`remove` doesn't exist | Error printed                            | `1`       |
| Unknown command, missing/invalid argument or priority, no command | Usage or error message on stderr | `2` |
| Blank title (`add ""`)                        | Rejected by the core layer with a `ValueError` | — |

### Where the data lives

Tasks are saved to `data/tasks.json`, created automatically on first save:

```json
[
  {"id": 1, "title": "Buy milk", "done": false},
  {"id": 2, "title": "Write report", "done": false, "priority": "high"}
]
```

You can point the app at a different file with the `TODO_DATA_FILE`
environment variable — this is also how the test suite avoids touching real
data:

```bash
TODO_DATA_FILE=/tmp/scratch.json python main.py add "Try me out"
```

## How the project works

The app is split into three thin layers:

1. **CLI — `main.py`**
   Parses one command (`add` / `list` / `done` / `remove`) plus its arguments
   with `argparse` (`add --priority`, `list --order/--done/--pending/
   --priority`), calls the core functions, saves the result, and prints a
   formatted line per task. All input/output lives here; this is the only
   file that prints or touches the process exit code.

2. **Logic — `todo/core.py`**
   Pure functions that operate on an in-memory list of task dicts:
   - `add_task` — assigns the next id (`max(existing ids) + 1`), rejects
     blank titles with `ValueError`, and stores an optional `priority`
     (omitted when it is the default)
   - `complete_task` — marks a task done, returns it (or `None` if the id is
     unknown)
   - `remove_task` — deletes a task, returns `True`/`False`
   - `list_tasks` — returns tasks sorted by `id` (default) or by
     `priority`/`status`
   - `filter_tasks` — returns tasks matching `priority` and/or `done`,
     raising `ValueError` for an unknown priority name
   - `get_priority`, `normalize_priority`, `priority_rank` — priority
     helpers shared by the above

   No printing, no file access — which makes these functions easy to unit
   test.

3. **Storage — `todo/storage.py`**
   `load_tasks` reads the JSON file (returning `[]` if it doesn't exist or is
   empty; malformed JSON still raises `json.JSONDecodeError`, so corruption is
   never silently ignored). `save_tasks` writes it back, creating parent
   directories if needed. The default path comes from the `TODO_DATA_FILE`
   environment variable or falls back to `data/tasks.json`.

The data flow for a command like `python main.py done 1` is:

```
main.py ──load_tasks()──▶ data/tasks.json        (read)
   │
   ├─ core.complete_task(tasks, 1)               (mutate in memory)
   │
   └──save_tasks()───────▶ data/tasks.json       (write back)
```

Because every command loads the file, changes the list in memory, and writes
it back, the JSON file is the single source of truth between invocations.

## Running the checks

```bash
python scripts/run_checks.py          # unit tests + a CLI smoke test
python -m unittest discover -s tests  # unit tests only
```

- `scripts/run_checks.py` first runs the unit tests in `tests/`, then drives
  `main.py` through a full add → list → done → remove sequence — including
  the priority flag, a `--priority high` filter and a deliberately rejected
  `--priority urgent` — as a smoke test, pointing `TODO_DATA_FILE` at a
  scratch file so real data is never touched. It also runs `pip check`,
  which exits non-zero if the installed environment has broken dependency
  requirements (e.g. a package version that contradicts what the lock file
  declares).
- `tests/test_core.py` — unit tests for the core logic (id assignment,
  blank-title rejection, completing, removing) plus a full priority suite
  (defaults, casing, invalid values, priority/status ordering, filters).
- `tests/test_storage.py` — unit tests for storage, using a temporary
  directory (missing/empty file handling, save/load round-trip, parent
  directory creation, valid JSON output, malformed-JSON error).

`python run_checks.py` still works as a backwards-compatible alias — the file
at the project root simply forwards to the script in `scripts/`.

## Project layout

```
.
├── main.py              CLI entry point (arg parsing, printing, exit codes)
├── run_checks.py        compatibility shim → scripts/run_checks.py
├── requirements.in      direct dependencies (hand-maintained source)
├── requirements.txt     pinned lock file (generated by pip-compile)
├── todo/                application package
│   ├── __init__.py      package exports
│   ├── core.py          task logic (add/complete/remove/list/filter)
│   └── storage.py       JSON load/save
├── tests/
│   ├── test_core.py     unit tests for the core logic + priority feature
│   └── test_storage.py  unit tests for JSON storage
├── scripts/
│   └── run_checks.py    unit tests + CLI smoke test + pip check
└── data/
    ├── tasks.json       runtime data (gitignored, created on first save)
    └── downloads/       directory for downloaded files (contents gitignored)
```

Build artifacts (`__pycache__/`) and the `data/` directory are ignored via
`.gitignore` (only the `data/downloads/README.md` placeholder is tracked, so
the folder exists after a fresh clone).
