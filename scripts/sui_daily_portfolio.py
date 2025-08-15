
### File: scripts/sui_daily_portfolio.py
#!/usr/bin/env python3
"""Daily Sui portfolio snapshot using public JSON‑RPC (plaintext outputs).
Outputs:
  - data/portfolio_<addrprefix>.csv  (append-only, 1 row per coin per day)
  - data/latest.json                 (full structured snapshot for easy reading)
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import pathlib
import typing as t
import urllib.request
import time

RPC_URL = os.environ.get('SUI_RPC_URL', 'https://fullnode.mainnet.sui.io:443')
ADDRESS = os.environ.get('SUI_ADDRESS', '0x9e10f69f6475bcb01fb2117facd665c68483da2cdefa6a681fa6a874af0df165')
OUT_DIR = pathlib.Path(os.environ.get('OUT_DIR', 'data'))
CSV_PATH = OUT_DIR / f'portfolio_{ADDRESS[:10]}.csv'
LATEST_JSON = OUT_DIR / 'latest.json'

# ---- JSON-RPC ----

def _rpc_once(method: str, params: t.List[t.Any]) -> t.Any:
    payload = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode('utf-8')
    req = urllib.request.Request(RPC_URL, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:  # stdlib only
        body = r.read().decode('utf-8')
    data = json.loads(body)
    if 'error' in data:
        raise RuntimeError(f"RPC error {data['error']}")
    return data['result']


def rpc(method: str, params: t.List[t.Any], retries: int = 3, backoff: float = 1.0) -> t.Any:
    for attempt in range(retries):
        try:
            return _rpc_once(method, params)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(backoff * (2 ** attempt))


def get_all_balances(address: str) -> t.List[dict]:
    return rpc('suix_getAllBalances', [address])


def get_coin_metadata(coin_type: str) -> dict:
    return rpc('suix_getCoinMetadata', [coin_type]) or {}


# ---- main ----

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    balances = get_all_balances(ADDRESS)
    balances = sorted(balances, key=lambda b: b.get('coinType', ''))  # stable diffs

    date_iso = dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    rows = []
    json_balances = []

    for b in balances:
        coin_type = b.get('coinType')
        raw = int(b.get('totalBalance', '0') or 0)
        meta = get_coin_metadata(coin_type)
        symbol = meta.get('symbol') or ''
        decimals = int(meta.get('decimals') or 9)
        human = raw / (10 ** decimals)

        rows.append({
            'date_iso': date_iso,
            'address': ADDRESS,
            'coin_type': coin_type,
            'symbol': symbol,
            'decimals': decimals,
            'raw_balance': raw,
            'human_balance': f"{human:.8f}",
        })
        json_balances.append({
            'coin_type': coin_type,
            'symbol': symbol,
            'decimals': decimals,
            'raw_balance': raw,
            'human_balance': human,
        })
        time.sleep(0.05)

    header = ['date_iso', 'address', 'coin_type', 'symbol', 'decimals', 'raw_balance', 'human_balance']
    write_header = not CSV_PATH.exists()
    with CSV_PATH.open('a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=header)
        if write_header:
            w.writeheader()
        for r in rows:
            w.writerow(r)

    LATEST_JSON.write_text(json.dumps({
        'date_iso': date_iso,
        'address': ADDRESS,
        'balances': json_balances
    }, indent=2))


if __name__ == '__main__':
    main()


