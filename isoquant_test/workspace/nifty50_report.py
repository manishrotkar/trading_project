"""Print the full NIFTY 50 row from the saved NSE allIndices payload."""
import json
from pathlib import Path

PATH = Path("data/downloads/nse_all_indices.json")
data = json.loads(PATH.read_text())
rows = data["data"]

nifty50 = next((r for r in rows if str(r.get("index", "")).upper() == "NIFTY 50"), None)
if nifty50 is None:
    raise SystemExit("FAIL: no NIFTY 50 row in payload")

print(f"server timestamp : {data.get('timestamp')}")
print("NIFTY 50 fields:")
for key in sorted(nifty50):
    print(f"  {key:<24} {nifty50[key]}")

print("\ntop gainers (of all indices):")
for r in sorted(rows, key=lambda r: r.get("percentChange") or 0, reverse=True)[:5]:
    print(f"  {r['index']:<28} {r['last']:>12}  {r['percentChange']:>7}%")

print("\ntop losers:")
for r in sorted(rows, key=lambda r: r.get("percentChange") or 0)[:5]:
    print(f"  {r['index']:<28} {r['last']:>12}  {r['percentChange']:>7}%")
