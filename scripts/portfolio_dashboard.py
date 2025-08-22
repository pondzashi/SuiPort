"""Generate an interactive HTML dashboard summarising portfolio totals.

Reads ``data/latest.json`` (produced by ``sui_daily_portfolio.py``) and writes a
``dashboard.html`` file that uses Chart.js to render a stacked bar chart of
wallet and Suilend balances for each address. No Python dependencies are
required beyond the standard library.
"""

import json
import pathlib
from string import Template


ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / 'data' / 'latest.json'
OUT_FILE = ROOT / 'dashboard.html'


HTML_TEMPLATE = Template(
    """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Portfolio Summary</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
  <h1>Portfolio Summary (Total $$total)</h1>
  <canvas id="chart" width="800" height="400"></canvas>
  <script>
    const labels = $labels;
    const wallet = $wallet;
    const suilend = $suilend;
    const ctx = document.getElementById('chart').getContext('2d');
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {label: 'Wallet USD', data: wallet, backgroundColor: 'rgba(54,162,235,0.5)'},
          {label: 'Suilend Net USD', data: suilend, backgroundColor: 'rgba(255,99,132,0.5)'}
        ]
      },
      options: {
        responsive: true,
        scales: {
          x: {stacked: true},
          y: {stacked: true}
        }
      }
    });
  </script>
</body>
</html>
"""
)


def load_data() -> tuple[list[str], list[float], list[float], float]:
    obj = json.loads(DATA_FILE.read_text())
    accounts = obj.get('accounts', [])
    labels: list[str] = []
    wallet_usd: list[float] = []
    suilend_net: list[float] = []
    for acc in accounts:
        labels.append(acc.get('address', '')[:10])
        wallet_usd.append(acc.get('totals', {}).get('wallet_usd', 0.0))
        suilend_summary = ((acc.get('defi') or {}).get('suilend_summary') or {})
        suilend_net.append(suilend_summary.get('net_usd', 0.0))
    total = obj.get('totals_usd', {}).get('portfolio_total', 0.0)
    return labels, wallet_usd, suilend_net, total


def make_dashboard() -> None:
    labels, wallet_usd, suilend_net, total = load_data()
    html = HTML_TEMPLATE.substitute(
        labels=json.dumps(labels),
        wallet=json.dumps(wallet_usd),
        suilend=json.dumps(suilend_net),
        total=f"{total:.2f}",
    )
    OUT_FILE.write_text(html)
    print(f'Wrote {OUT_FILE}')


if __name__ == '__main__':
    make_dashboard()
