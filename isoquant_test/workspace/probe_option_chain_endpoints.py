"""Diagnostic: probe NSE option-chain endpoint variants.

Identifies whether HTTP 404 comes from a wrong URL shape or from
Akamai blocking the API path.
"""
import urllib.error
import urllib.request

HOST = "www.nseindia.com"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"https://{HOST}/",
}

CANDIDATES = [
    "https://{h}/api/option-chain-indices?symbol=NIFTY",
    "https://{h}/api/option-chain-v3?symbol=NIFTY",
    "https://{h}/api/option-chain-indices?symbol=NIFTY&expiry=",
    "https://{h}/api/allIndices",          # known-good control
    "https://{h}/api/equity-stockIndices?index=NIFTY%2050",
]

for template in CANDIDATES:
    url = template.format(h=HOST)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            size = len(resp.read())
            print(f"HTTP {resp.status}  {size:>9,} bytes  {url}")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read(120).decode("utf-8", "replace").strip()
        except Exception:
            pass
        print(f"HTTP {exc.code}  ---         {url}  body={body[:60]!r}")
    except Exception as exc:
        print(f"ERR      ---         {url}  {exc}")
