# SuiPort

Scripts for collecting and visualising Sui portfolio data.

## Dashboard

Generate an interactive dashboard summarising the latest portfolio snapshot.

```
python scripts/portfolio_dashboard.py
```

This reads `data/latest.json` and writes `dashboard.html` using Chart.js with a
stacked bar chart of wallet and Suilend balances for each configured address.
