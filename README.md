# SuiPort

Scripts for collecting and visualising Sui portfolio data.

## Quick Summary

Print a simple wallet overview for one or more addresses via the Sui
JSON‑RPC.  If Suilend snapshot files (`data/suilend_<addrprefix>.json`) are
present, their deposit and borrow positions are summarised as well.  The
script tolerates RPC/pricing network failures and will continue with whatever
data is available:

```
SUI_ADDRESSES=addr1,addr2 python scripts/portfolio_summary.py
```

If `SUI_ADDRESSES` is not provided, the script uses example addresses defined
in the file.

## Protocol Data

Fetch raw positions for specific DeFi protocols. Set `SUI_ADDRESSES` to a
comma-separated list of Sui addresses and run:

```
SUI_ADDRESSES=addr1,addr2 python scripts/fetch_protocol_data.py
```

This writes JSON responses from Suilend, Cetus, and Aftermath into the `data`
directory for each address.

## Dashboard

Generate an interactive dashboard summarising the latest portfolio snapshot.

```
python scripts/portfolio_dashboard.py
```

This reads `data/latest.json` and writes `dashboard.html` using Chart.js with a
stacked bar chart of wallet and Suilend balances for each configured address.

## Daily automation

The repository contains a GitHub Actions workflow that refreshes the portfolio
snapshot every day at 09:00 Bangkok time (02:00 UTC). The job runs
`scripts/run_daily_snapshot.py`, which:

1. Pulls on-chain balances for the address supplied via `SUI_ADDRESSES` and
   stores raw results in `data/` (per-address CSVs plus `latest.json`).
2. Builds a Markdown summary and writes it to `data/latest_report.md`.

When the workflow detects new data it commits the updated files back to the
repository automatically. You can trigger it manually from the Actions tab
using the **Run workflow** button.
