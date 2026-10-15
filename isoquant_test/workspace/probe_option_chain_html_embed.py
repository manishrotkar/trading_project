"""Check whether the option-chain HTML page embeds chain data.

The /option-chain page returns HTTP 200 (338 KB) here.  If NSE server-side
renders the option chain into that HTML, the data could be extracted even
though the JSON API is blocked.  This probe downloads the page and searches
it for option-chain-shaped JSON keys.
"""
import json
import re
import urllib.error
import urllib.request

HOST = "www.nseindia.com"
PAGE = f"https://{HOST}/option-chain"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"https://{HOST}/",
}

# Strings that would appear in an embedded option-chain payload.
MARKERS = [
    "strikePrice", "expiryDates", "underlyingValue", "openInterest",
    "impliedVolatility", "strikeData", "optionchain", "PCR",
]

req = urllib.request.Request(PAGE, headers=HEADERS)
with urllib.request.urlopen(req, timeout=30) as resp:
    html = resp.read().decode("utf-8", "replace")
print(f"downloaded {len(html):,} bytes from {PAGE}")

# Any embedded JSON blobs (script payloads) at all?
blobs = re.findall(r"<script[^>]*type=\"application/json\"[^>]*>(.*?)</script>",
                   html, re.S)
print(f"application/json script blobs: {len(blobs)}")

found = {m: len(re.findall(m, html, re.I)) for m in MARKERS}
print("option-chain marker occurrences in HTML:")
for marker, count in found.items():
    print(f"  {marker:<20} {count}")

if any(found.values()):
    # Show a short context around the first hit of each non-zero marker.
    for marker, count in found.items():
        if count:
            i = html.lower().find(marker.lower())
            print(f"\nfirst {marker!r} context: ...{html[max(0, i-80):i+120]!r}...")
    print("\nVERDICT: possible embedded data -- inspect manually")
else:
    print("\nVERDICT: no option-chain data embedded in the HTML "
          "(the page fetches the blocked API client-side)")
