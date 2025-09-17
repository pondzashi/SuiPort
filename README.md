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
