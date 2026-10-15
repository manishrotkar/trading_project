"""Inspect the structure of the NSE India allIndices payload."""
import json
from pathlib import Path

path = Path("data/downloads/nse_all_indices.json")
if not path.exists():
    raise SystemExit("run fetch_nse_indices.py first (it saves the file)")

data = json.loads(path.read_bytes())
print("top-level keys :", sorted(data.keys()))
print("timestamp      :", data.get("timestamp"))

rows = data["data"]
print("rows           :", len(rows))
print("\nfirst row keys :", sorted(rows[0].keys()))
print("\nall index names:")
for r in rows:
    print("  -", repr(r.get("index")))
