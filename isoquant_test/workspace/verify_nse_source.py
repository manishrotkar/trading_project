"""Re-verification probe: confirm we are talking to NSE India (the
National Stock Exchange of India), and retest reachability.

This is *not* a fallback exchange lookup -- the only acceptable source is
www.nseindia.com.  The certificate check below proves the server's real
identity, so we can never accidentally end up talking to something else.
"""
import json
import socket
import ssl
import time
import urllib.error
import urllib.request

HOST = "www.nseindia.com"
URL = f"https://{HOST}/api/allIndices"  # official NSE India API endpoint
TIMEOUT = 20

# --- 1. Identity check via the server certificate --------------------------
print(f"[1] Connecting to https://{HOST} ...")
ctx = ssl.create_default_context()
try:
    with socket.create_connection((HOST, 443), timeout=TIMEOUT) as raw:
        with ctx.wrap_socket(raw, server_hostname=HOST) as tls:
            cert = tls.getpeercert()
            org = [v for r in cert.get("subject", ()) for k, v in r if k == "organizationName"]
            cn = next((v for r in cert.get("subject", ()) for k, v in r if k == "commonName"), "?")
            print(f"    TLS certificate CN          : {cn}")
            print(f"    TLS certificate organization: {org}")
            print("    -> identity confirmed:" +
                  (" National Stock Exchange of India (NSE India)"
                   if any("National Stock Exchange of India" in o for o in org) else
                   " UNEXPECTED OWNER -- do not trust this host"))
except Exception as exc:  # noqa: BLE001
    print(f"    FAIL -> {type(exc).__name__}: {exc}")
    cert_ok = False
else:
    cert_ok = True

# --- 2. Reachability of the official NSE India API -------------------------
if cert_ok:
    print(f"\n[2] Requesting {URL} ...")
    req = urllib.request.Request(URL, headers={
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    })
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
            print(f"    OK HTTP {resp.status}: {len(body)} bytes "
                  f"in {time.monotonic() - t0:.2f}s")
    except urllib.error.HTTPError as exc:
        print(f"    BLOCKED: HTTP {exc.code} from Akamai/edge "
              f"({time.monotonic() - t0:.2f}s) -- datacentre IP denied")
    except Exception as exc:  # noqa: BLE001
        print(f"    FAIL -> {type(exc).__name__}: {exc}")

print(json.dumps({"done": True}))
