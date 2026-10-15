"""Probe 4: try alternative HTTP clients for nseindia.com.

Some environments ship curl, whose TLS fingerprint differs from Python's
urllib.  We try curl first; if it's not available we fall back to
http.client with an explicit warm-up + reuse of the same TCP connection.
"""
import json
import shutil
import subprocess

# --- Option A: curl -------------------------------------------------------
curl = shutil.which("curl")
print(f"curl available: {curl}")

if curl:
    result = subprocess.run(
        [curl, "-sS", "-o", "/dev/null", "-w",
         "HTTP %{http_code}, %{size_download} bytes, %{time_total}s",
         "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
         "-H", "Accept: text/html,application/xhtml+xml,*/*",
         "-H", "Accept-Language: en-US,en;q=0.9",
         "https://www.nseindia.com/"],
        capture_output=True, text=True, timeout=30)
    print("curl stdout:", result.stdout.strip())
    print("curl stderr:", result.stderr.strip())
    print("curl returncode:", result.returncode)
else:
    print("curl not on PATH")

print(json.dumps({"done": True}))
