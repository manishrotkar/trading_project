"""Retest whether NSE India's option-chain API is reachable today.

NSE_BLOCKED_NOTES.md records that the option-chain endpoints returned
HTTP 404 (Akamai block) while /api/allIndices returned 200.  Blocks can
change over time, so this script re-runs the checks:

  1. TLS identity check  -- proves the host really is NSE India.
  2. Warm-up visit       -- GET /option-chain to obtain cookies.
  3. Option-chain API    -- /api/option-chain-indices?symbol=NIFTY
                            with and without the warm-up cookies.
  4. Decoy check         -- /api/option-chain-v3 (200 with `{}` body).
  5. Control             -- /api/allIndices must still be healthy.

Output is a JSON verdict on the last line:
  {"option_chain_ok": true/false, "reason": "..."}
"""
import http.cookiejar
import json
import socket
import ssl
import time
import urllib.error
import urllib.request

HOST = "www.nseindia.com"
SYMBOL = "NIFTY"
TIMEOUT = 30

BASE_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"https://{HOST}/",
}


def verdict(ok: bool, reason: str) -> None:
    print(json.dumps({"option_chain_ok": ok, "reason": reason}))


def identity_check() -> bool:
    print(f"[1] TLS identity of {HOST}")
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((HOST, 443), timeout=TIMEOUT) as raw:
            with ctx.wrap_socket(raw, server_hostname=HOST) as tls:
                cert = tls.getpeercert()
        orgs = [v for r in cert.get("subject", ()) for k, v in r
                if k == "organizationName"]
        print(f"    certificate organization: {orgs}")
        if not any("National Stock Exchange of India" in o for o in orgs):
            print("    FAIL: unexpected certificate owner -- aborting")
            return False
        print("    OK: host is NSE India")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"    FAIL: {type(exc).__name__}: {exc}")
        return False


def make_opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar


def fetch(opener, url: str, accept: str):
    req = urllib.request.Request(url, headers=dict(BASE_HEADERS, Accept=accept))
    t0 = time.monotonic()
    with opener.open(req, timeout=TIMEOUT) as resp:
        return resp.status, resp.read(), time.monotonic() - t0


def looks_like_option_chain(body: bytes) -> bool:
    """True if the payload has the real option-chain shape."""
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    records = data.get("records")
    return (isinstance(records, dict)
            and bool(records.get("data"))
            and bool(records.get("expiryDates")))


def main() -> None:
    if not identity_check():
        verdict(False, "identity check failed")
        return

    opener, jar = make_opener()

    # ---- 2. warm-up ------------------------------------------------------
    warm = f"https://{HOST}/option-chain"
    print(f"\n[2] Warm-up: GET {warm}")
    try:
        status, body, _ = fetch(opener, warm, "text/html,application/xhtml+xml,*/*")
        print(f"    HTTP {status}, {len(body):,} bytes, {len(jar)} cookie(s)")
    except urllib.error.HTTPError as exc:
        print(f"    warm-up blocked: HTTP {exc.code} (continuing without cookies)")
    except Exception as exc:  # noqa: BLE001
        print(f"    warm-up failed: {exc}")

    # ---- 3. the option-chain API ----------------------------------------
    api = (f"https://{HOST}/api/option-chain-indices?"
           + urllib.parse.urlencode({"symbol": SYMBOL}))
    print(f"\n[3] Option-chain API: GET {api}")
    try:
        status, body, elapsed = fetch(
            opener, api, "application/json, text/plain, */*")
        real = looks_like_option_chain(body)
        print(f"    HTTP {status}, {len(body):,} bytes in {elapsed:.2f}s, "
              f"option-chain shape: {real}")
        if real:
            verdict(True, "option-chain API returned real data")
            return
        snippet = body[:100].decode("utf-8", "replace")
        print(f"    body starts with: {snippet!r}")
        verdict(False, f"HTTP {status} but body is not option-chain data")
        return
    except urllib.error.HTTPError as exc:
        print(f"    BLOCKED: HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        print(f"    FAIL: {type(exc).__name__}: {exc}")

    # ---- 4. decoy endpoint, for the record -------------------------------
    decoy = f"https://{HOST}/api/option-chain-v3?symbol={SYMBOL}"
    print(f"\n[4] Decoy check: GET {decoy}")
    try:
        status, body, _ = fetch(opener, decoy, "application/json, text/plain, */*")
        print(f"    HTTP {status}, body: {body[:40].decode('utf-8', 'replace')!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"    {type(exc).__name__}: {exc}")

    # ---- 5. control ------------------------------------------------------
    control = f"https://{HOST}/api/allIndices"
    print(f"\n[5] Control: GET {control}")
    try:
        status, body, _ = fetch(opener, control, "application/json")
        print(f"    HTTP {status}, {len(body):,} bytes")
        if status == 200 and len(body) > 10_000:
            verdict(False, "option-chain API blocked; allIndices still works")
        else:
            verdict(False, "option-chain API blocked; allIndices degraded too")
    except Exception as exc:  # noqa: BLE001
        verdict(False, f"option-chain API blocked; control failed: {exc}")


import urllib.parse  # noqa: E402  (used above in main)

if __name__ == "__main__":
    main()
