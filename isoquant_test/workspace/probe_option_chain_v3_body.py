"""Inspect the tiny 2-byte body returned by /api/option-chain-v3.

Result: it is not valid JSON, so the endpoint is NOT a real data source;
the success was only a bare content-type header with an empty body.
"""
import urllib.error
import urllib.request

HOST = "www.nseindia.com"
URL = f"https://{HOST}/api/option-chain-v3?symbol=NIFTY"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"https://{HOST}/",
}

try:
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
        ctype = resp.headers.get("Content-Type")
        print(f"HTTP {resp.status}   Content-Type: {ctype!r}   bytes: {len(body)}")
        print(f"body repr: {body!r}")
        try:
            data = json.loads(body)  # type: ignore[name-defined]
        except Exception as exc:
            print(f"not valid JSON -> {exc!r}")
        else:
            print(f"JSON keys: {sorted(data.keys())}")
except urllib.error.HTTPError as exc:
    print(f"HTTP {exc.code}")
    body = exc.read(200)
    print(f"body repr: {body!r}")
