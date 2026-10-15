# NSE Option-Chain API — Blocked Access Notes

Investigation notes on the NSE India option-chain endpoint that
`fetch_nifty50_options.py` tries to use. The conclusion from the probe
scripts listed in `PROJECT_STRUCTURE.md` § 6:

- **Endpoint**: `https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY`
- **Result**: **HTTP 404** from this environment, consistently, both with and
  without cookie warm-up, browser-like headers, and retrying across days.
- **What does work**: `https://www.nseindia.com/api/allIndices` (used by
  `nifty50_options_summary.py`), and the official **FO bhavcopy archives**
  (used by `fetch_nifty50_option_contracts.py`).

Because the blocked endpoint is the only source of live option quotes, the
project does this instead:

| Want | Do this instead | Script |
|---|---|---|
| Underlying spot / change | NSE allIndices | `nifty50_options_summary.py` |
| Open interest by strike | NSE FO bhavcopy (end of day) | `nifty50_open_interest.py` |
| Expiry dates | Computed from the calendar, or the bhavcopy | `nifty50_expiries.py` |

No fallback to any other data provider is permitted — scripts fail loudly
when NSE blocks them.
