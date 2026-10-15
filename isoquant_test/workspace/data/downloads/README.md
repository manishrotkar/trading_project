# Data

Runtime data for the to-do app and downloads for the market-data scripts.

```
data/
├── tasks.json            to-do app storage (created on first save, gitignored)
└── downloads/            artifacts fetched by the market-data scripts
    └── README.md         tracked placeholder so this folder exists in git
```

- `tasks.json` — the single source of truth for the to-do app. Format:
  `[{"id": 1, "title": "...", "done": false}]`. Override the path with the
  `TODO_DATA_FILE` environment variable.
- `downloads/` — everything produced by `download_nifty_options.py` and the
  `fetch_*` / `probe_*` scripts. Only `README.md` is tracked; all downloads
  are gitignored. Key files:

| File | Written by | Contents |
|---|---|---|
| `nse_all_indices.json` | `fetch_nse_indices.py` | raw NSE allIndices payload |
| `nifty50_options_summary.json` | `nifty50_options_summary.py` | derived option summary (spot, ATM strike, synthetic prices, expiries) |
| `nse_nifty50_option_contracts.csv` | `fetch_nifty50_option_contracts.py` | official NSE FO bhavcopy rows |
| `nifty50_option_chain_status.json` | `fetch_nifty50_option_contracts.py` | fetch status: as_of date, nearest expiry |
| `ltp.json`, `nifty50_bid_ask.json` | `ltp.py`, `bid_ask.py` | quote payloads built by the Fyers tooling |

`NSE_BLOCKED_NOTES.md` at the project root explains why live option-chain
quotes cannot be fetched here and what the project uses instead.
