"""Probe whether NSE's official archive hosts are reachable.

The daily FO bhavcopy (published by NSE itself) contains the complete
option-contract market data for the day: every strike with CE/PE
settlement prices, open interest, volume and more.  It lives on
nsearchives.nseindia.com / archives.nseindia.com -- still NSE India,
the required source, just a different host from the blocked
www.nseindia.com/api/option-chain-* endpoints.

This probe checks reachability of both hosts.  No data is fetched yet.
"""
import datetime as dt
import urllib.error
import urllib.request

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


def try_url(url: str) -> None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            head = resp.read(64)
            print(f"HTTP {resp.status}  ct={resp.headers.get('Content-Type')!r}  "
                  f"{url}  head={head[:32]!r}")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read(80).decode("utf-8", "replace").strip()
        except Exception:
            pass
        print(f"HTTP {exc.code}  {url}  body={body[:60]!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"ERR      {url}  {type(exc).__name__}: {exc}")


today = dt.date.today()
stamp = today.strftime("%Y%m%d")            # YYYYMMDD for UDiFF bhavcopy
legacy = today.strftime("%d%m%Y")           # DDMMYYYY for the legacy file
print(f"today = {today} ({today.strftime('%A')})")

# UDiFF-format daily FO bhavcopy on the current archive host.
try_url(f"https://nsearchives.nseindia.com/content/fo/"
        f"BhavCopy_NSE_FO_0_0_0_{stamp}_F_0000.csv.zip")
# Legacy-format FO bhavcopy on the old archive host.
try_url(f"https://archives.nseindia.com/content/fo/fo{legacy}bhav.csv.zip")
# Host-level reachability control (a small known file on each host).
try_url("https://nsearchives.nseindia.com/content/indices/ind_close_all_"
        + today.strftime("%d%m%Y") + ".csv")
