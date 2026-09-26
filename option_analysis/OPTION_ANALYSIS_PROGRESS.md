# Option Analysis - Progress Summary

## Project
`~/trading_project/option_analysis/`

Focus:
- NIFTY + BANKNIFTY
- 1-minute option analysis
- Existing FYERS data is the main source
- No Docker for now
- `futures_project` is read-only for analysis

## Completed
- `database/index_options.db`: NIFTY/BANKNIFTY 1-minute option OHLC + Volume + OI, selected ATM ±20 strikes, nearest expiry, Sep 1-25 2026.
- `database/underlying_data.db`: NIFTY/BANKNIFTY 1-minute underlying data and INDIA VIX.
- `database/fyers_style_iv.db`: Black-76 IV using futures price and OTM options.
- `database/iv_analysis.db`: ATM IV, IV Rank, IV Percentile and actual lookback days.
- `database/oi_analysis.db`: strike OI, OI change, OI %, price change, activity, ATM OI, selected-chain Total PCR, OI concentration, activity balance, market trend, combined market analysis, market state and corrected same-day forward 5-candle returns.
- Development/validation analysis was completed. Current sample is only 18 trading days, so it is not enough to establish a reliable trading relationship.

## Activity rules
- Price up + OI up = LONG_BUILDUP
- Price down + OI up = SHORT_BUILDUP
- Price up + OI down = SHORT_COVERING
- Price down + OI down = LONG_UNWINDING

## Important decision
NSE was checked only because FYERS historical candles do not provide historical OI. NSE contract-wise historical data is daily, not 1-minute, and would require contract-wise handling.

We are NOT switching to NSE and NOT manually downloading thousands of contracts.

Continue with the existing FYERS-based project/database.

## FYERS limitation
- History API: historical OHLC + volume, not historical OI in candle response.
- Optionchain: current/live OI and Greeks, not historical intraday OI.

## Do NOT touch
- `~/trading_project/futures_project/`
- Existing databases unless a specific analysis requires an update
- Git history unless explicitly required
- No Docker

## After PC restart
```bash
cd ~/trading_project
source .venv/bin/activate
which python
python --version
cd ~/trading_project/option_analysis
git status
```

Expected Python:
`/home/manish/trading_project/.venv/bin/python`
`Python 3.13.11`

## Immediate next step
Continue the existing FYERS-based option analysis. First identify the next missing analysis/data component before writing code.

Do NOT start another NSE download experiment.
Do NOT change the futures project.
Do NOT touch Git unless explicitly required.
