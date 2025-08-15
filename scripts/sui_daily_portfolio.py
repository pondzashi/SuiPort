from __future__ import annotations

import csv
import datetime as dt
import json
import os
import pathlib
import typing as t
import urllib.request
import time
from urllib.error import URLError

RPC_URL = os.environ.get('SUI_RPC_URL', 'https://fullnode.mainnet.sui.io:443')
ADDRS_ENV = os.environ.get('SUI_ADDRESSES') or os.environ.get('SUI_ADDRESS') or ''
ADDRESSES = [a.strip() for a in ADDRS_ENV.split(',') if a.strip()]
if not ADDRESSES:
    ADDRESSES = ['0x9e10f69f6475bcb01fb2117facd665c68483da2cdefa6a681fa6a874af0df165,0xa63ef51b8abf601fb40d8514050a8d5613c0509d4b36323dc4439ee6c69d704e']
# de-duplicate while preserving order
seen = set()
ADDRESSES = [a for a in ADDRESSES if not (a in seen or seen.add(a))]
OUT_DIR = pathlib.Path(os.environ.get('OUT_DIR', 'data'))

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

# ---- Pricing (CoinGecko) ----

CG_IDS = {
    'sui': 'sui',
    'ssui': 'sui',
    'vsui': 'sui',
    'hasui': 'sui',
    'usdc': 'usd-coin',
    'usdt': 'tether',
    'sol': 'solana',
}


def fetch_prices_cg(ids: t.Set[str]) -> dict:
    if not ids:
        return {}
    q = ','.join(sorted(ids))
    url = f'https://api.coingecko.com/api/v3/simple/price?ids={q}&vs_currencies=usd'
    req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'portfolio-bot/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode('utf-8'))
            return {k: float(v.get('usd', 0)) for k, v in data.items()}
    except URLError:
        return {}


def symbol_to_cg_id(sym: str) -> str | None:
    return CG_IDS.get((sym or '').lower())


def coin_price_usd(symbol: str, price_map: dict) -> float | None:
    cid = symbol_to_cg_id(symbol)
    if not cid:
        return None
    p = price_map.get(cid)
    return float(p) if p is not None else None


# ---- Helpers ----

def addr_prefix(addr: str) -> str:
    return addr[:10]


# ---- main ----

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Pull wallet balances for all addresses
    accounts: list[dict] = []
    symbols_needed: set[str] = set()

    for address in ADDRESSES:
        csv_path = OUT_DIR / f'portfolio_{addr_prefix(address)}.csv'
        balances = get_all_balances(address)
        balances = sorted(balances, key=lambda b: b.get('coinType', ''))
        date_iso = dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

        rows_csv = []
        rows_json = []
        for b in balances:
            coin_type = b.get('coinType')
            raw = int(b.get('totalBalance', '0') or 0)
            meta = get_coin_metadata(coin_type)
            symbol = meta.get('symbol') or ''
            decimals = int(meta.get('decimals') or 9)
            human = raw / (10 ** decimals)
            rows_csv.append({
                'date_iso': date_iso,
                'address': address,
                'coin_type': coin_type,
                'symbol': symbol,
                'decimals': decimals,
                'raw_balance': raw,
                'human_balance': f"{human:.8f}",
            })
            rows_json.append({
                'coin_type': coin_type,
                'symbol': symbol,
                'decimals': decimals,
                'raw_balance': raw,
                'human_balance': human,
            })
            if symbol:
                symbols_needed.add(symbol)
            time.sleep(0.02)

        # write CSV per address
        header = ['date_iso', 'address', 'coin_type', 'symbol', 'decimals', 'raw_balance', 'human_balance']
        write_header = not csv_path.exists()
        with csv_path.open('a', newline='') as f:
            w = csv.DictWriter(f, fieldnames=header)
            if write_header:
                w.writeheader()
            for r in rows_csv:
                w.writerow(r)

        # Suilend attachment path for this address
        suilend_path = OUT_DIR / f'suilend_{addr_prefix(address)}.json'
        suilend_obj = None
        if suilend_path.exists():
            try:
                suilend_obj = json.loads(suilend_path.read_text())
                # collect symbols from simplified deposits/borrows if present
                for ob in suilend_obj.get('obligations', []):
                    for item in (ob.get('deposits') or []):
                        if item.get('symbol'): symbols_needed.add(item['symbol'])
                    for item in (ob.get('borrows') or []):
                        if item.get('symbol'): symbols_needed.add(item['symbol'])
            except Exception as e:
                suilend_obj = { 'error': str(e) }

        accounts.append({
            'address': address,
            'date_iso': date_iso,
            'balances': rows_json,
            'defi': { 'suilend': suilend_obj }
        })

    # 2) Fetch prices
    cg_ids = { cid for sym in symbols_needed if (cid := symbol_to_cg_id(sym)) }
    prices = fetch_prices_cg(cg_ids)

    # 3) Compute USD fields + totals per account
    grand_total_wallet_usd = 0.0
    grand_total_suilend_net_usd = 0.0

    for acc in accounts:
        # wallet
        wallet_total = 0.0
        for it in acc['balances']:
            price = coin_price_usd(it['symbol'], prices)
            usd = (it['human_balance'] * price) if price is not None else None
            it['usd_price'] = price
            it['usd_value'] = round(usd, 6) if usd is not None else None
            if usd is not None:
                wallet_total += usd
        acc['totals'] = { 'wallet_usd': round(wallet_total, 6) }
        grand_total_wallet_usd += wallet_total

        # suilend
        suilend = acc['defi'].get('suilend') or {}
        deposits_usd = 0.0
        borrows_usd = 0.0
        items = []
        for ob in suilend.get('obligations', []) or []:
            for kind, arr in [('deposit', ob.get('deposits') or []), ('borrow', ob.get('borrows') or [])]:
                for x in arr:
                    sym = x.get('symbol') or ''
                    dec = int(x.get('decimals') or 9)
                    human = x.get('amountHuman')
                    if human is None:
                        raw = int(x.get('amountRaw') or 0)
                        human = raw / (10 ** dec)
                    price = coin_price_usd(sym, prices)
                    usd = (human * price) if price is not None else None
                    items.append({ 'kind': kind, 'symbol': sym, 'decimals': dec, 'amount': human, 'usd_price': price, 'usd_value': (round(usd,6) if usd is not None else None) })
                    if usd is not None:
                        if kind == 'deposit': deposits_usd += usd
                        else: borrows_usd += usd
        suilend_summary = {
            'deposits_usd': round(deposits_usd, 6),
            'borrows_usd': round(borrows_usd, 6),
            'net_usd': round(deposits_usd - borrows_usd, 6),
            'items': items,
        }
        acc['defi']['suilend_summary'] = suilend_summary
        grand_total_suilend_net_usd += (deposits_usd - borrows_usd)

    # 4) Write latest.json with totals
    now_iso = dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    latest = {
        'date_iso': now_iso,
        'accounts': accounts,
        'prices_usd': prices,
        'totals_usd': {
            'wallet_sum': round(grand_total_wallet_usd, 6),
            'suilend_net': round(grand_total_suilend_net_usd, 6),
            'portfolio_total': round(grand_total_wallet_usd + grand_total_suilend_net_usd, 6),
        }
    }

    (OUT_DIR / 'latest.json').write_text(json.dumps(latest, indent=2))


if __name__ == '__main__':
    main()

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

    balances = get_all_balances(address)
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
        time.sleep(0.03)

    header = ['date_iso', 'address', 'coin_type', 'symbol', 'decimals', 'raw_balance', 'human_balance']
    write_header = not CSV_PATH.exists()
    with CSV_PATH.open('a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=header)
        if write_header:
            w.writeheader()
        for r in rows:
            w.writerow(r)

    # Merge Suilend if file present (created by Node step)
    suilend: dict | None = None
    if SUILEND_PATH.exists():
        try:
            suilend = json.loads(SUILEND_PATH.read_text())
        except Exception as e:  # keep going even if parsing fails
            suilend = {"error": str(e)}

    LATEST_JSON.write_text(json.dumps({
        'date_iso': date_iso,
        'address': ADDRESS,
        'balances': json_balances,
        'defi': {
            'suilend': suilend
        }
    }, indent=2))


if __name__ == '__main__':
    main()
