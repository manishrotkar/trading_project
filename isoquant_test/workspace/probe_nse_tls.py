"""Probe 3: what exactly happens with nseindia.com?

1. Plain DNS resolution.
2. TCP connect to 443.
3. TLS handshake — this is where Akamai usually terminates the connection
   for non-browser clients.
4. One attempt with a session-warm-up flow (cookie jar), with a longer
   timeout in case the connection is just very slow.
"""
import json
import socket
import ssl
import time
import urllib.error
import urllib.request

HOST = "www.nseindia.com"
URL = f"https://{HOST}/"

# --- 1. DNS ---------------------------------------------------------------
try:
    infos = socket.getaddrinfo(HOST, 443)
    addrs = sorted({i[4][0] for i in infos})
    print(f"DNS    {HOST} -> {addrs}")
except Exception as exc:  # noqa: BLE001
    print(f"DNS    FAIL -> {type(exc).__name__}: {exc}")
    addrs = []

# --- 2. TCP connect -------------------------------------------------------
if addrs:
    addr = addrs[0]
    try:
        t0 = time.monotonic()
        s = socket.create_connection((addr, 443), timeout=10)
        elapsed = time.monotonic() - t0
        print(f"TCP    connect to {addr}:443 OK in {elapsed:.2f}s")
        s.close()
    except Exception as exc:  # noqa: BLE001
        print(f"TCP    FAIL -> {type(exc).__name__}: {exc}")
        addrs = []

# --- 3. TLS handshake -----------------------------------------------------
if addrs:
    ctx = ssl.create_default_context()
    try:
        t0 = time.monotonic()
        with socket.create_connection((addrs[0], 443), timeout=10) as raw:
            with ctx.wrap_socket(raw, server_hostname=HOST) as tls:
                elapsed = time.monotonic() - t0
                cert = tls.getpeercert()
                print(f"TLS    handshake OK in {elapsed:.2f}s, "
                      f"proto={tls.version()}, cert CN={cert.get('subjectCN') or cert.get('subject')}")
    except Exception as exc:  # noqa: BLE001
        print(f"TLS    FAIL -> {type(exc).__name__}: {exc}")

# --- 4. Slow-but-real attempt ---------------------------------------------
headers = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
try:
    t0 = time.monotonic()
    req = urllib.request.Request(URL, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as resp:
        body = resp.read(200)
        print(f"HTTP   {URL} -> HTTP {resp.status}, {len(body)} bytes in "
              f"{time.monotonic() - t0:.2f}s")
except Exception as exc:  # noqa: BLE001
    print(f"HTTP   FAIL -> {type(exc).__name__}: {exc}")

print(json.dumps({"done": True}))
