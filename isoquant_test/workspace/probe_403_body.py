"""Probe 5: read the actual 403 body to see what kind of block it is.

Akamai challenges usually return a tiny HTML page with a 1x1 GIF reference
or a reference id like "18.3f2a1b02...".  A plain deny often returns
"Access Denied ... Event ID: ...".  Knowing which one it is tells us if a
session warm-up could ever work here.
"""
import json
import subprocess

result = subprocess.run(
    ["curl", "-sS", "-i",
     "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "https://www.nseindia.com/"],
    capture_output=True, text=True, timeout=30)

out = result.stdout
print(f"--- response ({len(out)} bytes) ---")
print(out[:2000])

print(json.dumps({"done": True}))
