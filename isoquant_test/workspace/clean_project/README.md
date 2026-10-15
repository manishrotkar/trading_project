# todoapp

A tiny command-line to-do application, structured as a clean, self-contained
project.

## Usage

Library:

```python
from todoapp import add_task

tasks = []
add_task(tasks, "Buy milk")
```

Command line:

```bash
python -m todoapp.cli add "Buy milk"
python -m todoapp.cli list
python -m todoapp.cli done 1
python -m todoapp.cli remove 1
```

The data file defaults to `data/tasks.json` (relative to the working
directory) and can be overridden per call with `--file <path>` or globally
with the `TODOAPP_DATA_FILE` environment variable.

## Tests

```bash
pytest                # or: python run_tests.py
```

## Project layout

```
clean_project/
├── pyproject.toml
├── README.md
├── todoapp/
│   ├── __init__.py
│   ├── core.py       # pure task logic
│   ├── storage.py    # JSON load/save
│   └── cli.py        # argparse CLI
└── tests/
    ├── test_core.py
    ├── test_storage.py
    └── test_cli.py
```
