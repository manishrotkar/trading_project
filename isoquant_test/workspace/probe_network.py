"""Probe 2: is the network blocked at the sandbox level?

Tests a few well-known hosts with very short timeouts so we do not sit
waiting for ages.  Prints one line per target.
"""
import json
import socket
import urllib.error
import urllib.request

TARGETS = [
    "https://www.example.com/",
    "https://www.google.com/",
    "https://httpbin.org/get",
]

socket.setdefaulttimeout(8)

for url in TARGETS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "probe/2"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read(200)
            print(f"OK   {url} -> HTTP {resp.status}, {len(body)} bytes read")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL {url} -> {type(exc).__name__}: {exc}")

print(json.dumps({"done": True}))
