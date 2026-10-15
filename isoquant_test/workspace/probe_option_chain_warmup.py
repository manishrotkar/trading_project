"""Diagnostic: does a cookie warm-up (visit the option-chain page first)
let the option-chain API return real data?

Expected per NSE_BLOCKED_NOTES.md: the HTML pages are Akamai-gated (403),
so warm-up cookies likely cannot be obtained -- but this verifies it.
"""
import http.cookiejar
import json
import urllib.error
import urllib.request

HOST = "www.nseindia.com"
WARMUP_URL = f"https://{HOST}/option-chain"
API_URL = f"https://{HOST}/api/option-chain-indices?symbol=NIFTY"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "application/json;q=0.9,*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"https://{HOST}/",
}

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def get(url: str, accept: str):
    headers = dict(HEADERS, Accept=accept)
    req = urllib.request.Request(url, headers=headers)
    with opener.open(req, timeout=30) as resp:
        return resp.status, resp.read()


# ---- warm-up -------------------------------------------------------------
try:
    status, body = get(WARMUP_URL, HEADERS["Accept"])
    print(f"warm-up : HTTP {status}, {len(body):,} bytes, "
          f"{len(jar)} cookie(s) stored")
except urllib.error.HTTPError as exc:
    print(f"warm-up : HTTP {exc.code} (blocked, no cookies obtained)")
except Exception as exc:
    print(f"warm-up : failed -- {exc}")

# ---- API with whatever cookies we have -----------------------------------
try:
    status, body = get(API_URL, "application/json, text/plain, */*")
    print(f"api     : HTTP {status}, {len(body):,} bytes")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print("api     : body is not JSON:", body[:80])
    else:
        keys = sorted(data.keys()) if isinstance(data, dict) else type(data).__name__
        print(f"api     : JSON keys: {keys}")
except urllib.error.HTTPError as exc:
    print(f"api     : HTTP {exc.code} (blocked)")
