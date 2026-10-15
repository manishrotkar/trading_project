# textstats

A tiny Python project that computes basic statistics about a text file.

## Install / run

```bash
cd new_project
pip install -e .
```

## Usage

Library:

```python
from textstats import analyze

print(analyze("Hello world\nHello again"))
```

Command line:

```bash
textstats sample.txt          # plain-text table
textstats sample.txt --json   # JSON output
```

## Tests

```bash
pip install pytest
pytest
```

## Project layout

```
new_project/
├── pyproject.toml
├── README.md
├── textstats/
│   ├── __init__.py
│   ├── core.py      # analysis functions
│   └── cli.py       # argparse CLI
└── tests/
    ├── test_core.py
    └── test_cli.py
```
