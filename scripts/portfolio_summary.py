import os
import json
import time
import urllib.request
from urllib.error import URLError
from pathlib import Path

SUI_RPC_URL = os.environ.get('SUI_RPC_URL', 'https://fullnode.mainnet.sui.io:443')
ADDRS_ENV = os.environ.get('SUI_ADDRESSES') or ''
ADDRESSES = [a.strip() for a in ADDRS_ENV.split(',') if a.strip()]
if not ADDRESSES:
    ADDRESSES = [
        '0xa63ef51b8abf601fb40d8514050a8d5613c0509d4b36323dc4439ee6c69d704e',
    ]

def rpc_call(method: str, params: list) -> dict:
    payload = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': method,
        'params': params,
    }
    data_bytes = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        SUI_RPC_URL, data=data_bytes, headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except URLError as e:  # network issues should not crash the script
        raise RuntimeError(f"network error: {e}")
    if 'error' in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data['result']

def get_all_balances(address: str) -> list:
    return rpc_call('suix_getAllBalances', [address])

def get_coin_metadata(coin_type: str) -> dict | None:
    try:
        return rpc_call('suix_getCoinMetadata', [coin_type])
    except RuntimeError:
        return None

# CoinGecko id mapping for pricing
CG_IDS = {
    'sui': 'sui',
    'ssui': 'sui',
    'vsui': 'sui',
    'hasui': 'sui',
    'usdc': 'usd-coin',
    'usdt': 'tether',
    'sol': 'solana',
}

def fetch_prices(symbols: set[str]) -> dict:
    id_map = {s: CG_IDS[s.lower()] for s in symbols if s.lower() in CG_IDS}
    if not id_map:
        return {}
    ids = ','.join(sorted(set(id_map.values())))
    url = f'https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd'
    req = urllib.request.Request(
        url, headers={'Accept': 'application/json', 'User-Agent': 'portfolio-bot/1.0'}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except URLError:
        return {}
    prices = {}
    for sym, cid in id_map.items():
        price = data.get(cid, {}).get('usd')
        if price is not None:
            prices[sym] = float(price)
    return prices

def summarize_suilend(addr: str, symbols: set[str]) -> dict | None:
    """Read Suilend data from data/suilend_<addrprefix>.json if present."""
    path = Path('data') / f'suilend_{addr[:10]}.json'
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text())
    except Exception as e:  # noqa: BLE001
        return {'error': str(e)}
    deposits = []
    borrows = []
    for ob in obj.get('obligations', []) or []:
        for item in ob.get('deposits') or []:
            sym = item.get('symbol') or ''
            if not sym:
                ct = (item.get('coinType') or {}).get('name', '')
                sym = ct.split('::')[-1]
            dec = int(item.get('decimals') or 9)
            amt = item.get('amountHuman')
            if amt is None:
                amt = int(item.get('amountRaw') or 0) / (10 ** dec)
            deposits.append({'symbol': sym, 'amount': amt})
            if sym:
                symbols.add(sym)
        for item in ob.get('borrows') or []:
            sym = item.get('symbol') or ''
            if not sym:
                ct = (item.get('coinType') or {}).get('name', '')
                sym = ct.split('::')[-1]
            dec = int(item.get('decimals') or 9)
            amt = item.get('amountHuman')
            if amt is None:
                amt = int(item.get('amountRaw') or 0) / (10 ** dec)
            borrows.append({'symbol': sym, 'amount': amt})
            if sym:
                symbols.add(sym)
    return {'deposits': deposits, 'borrows': borrows}


def main() -> None:
    results = []
    symbols: set[str] = set()
    for addr in ADDRESSES:
        try:
            balances = get_all_balances(addr)
        except RuntimeError as e:
            balances = []
            print(f"\nAddress {addr} (wallet fetch failed: {e})")
        entries = []
        for b in balances:
            coin_type = b.get('coinType')
            raw = int(b.get('totalBalance', '0') or 0)
            meta = get_coin_metadata(coin_type) or {}
            symbol = meta.get('symbol') or coin_type.split('::')[-1]
            decimals = int(meta.get('decimals') or 0)
            human = raw / (10 ** decimals) if decimals >= 0 else raw
            entries.append({'symbol': symbol, 'balance': human, 'coin_type': coin_type})
            if symbol:
                symbols.add(symbol)
            time.sleep(0.02)
        defi = summarize_suilend(addr, symbols)
        results.append({'address': addr, 'entries': entries, 'suilend': defi})
    prices = fetch_prices(symbols)
    for res in results:
        addr = res['address']
        if res.get('entries'):
            print(f"\nAddress {addr}")
        total_usd = 0.0
        for e in res.get('entries', []):
            sym = e['symbol']
            bal = e['balance']
            price = prices.get(sym)
            usd_val = bal * price if price is not None else None
            if usd_val is not None:
                total_usd += usd_val
                print(f"  - {sym}: {bal:.8f} (≈ ${usd_val:.2f})")
            else:
                print(f"  - {sym}: {bal:.8f}")
        if res.get('suilend'):
            s = res['suilend']
            if s.get('deposits') or s.get('borrows'):
                print("  Suilend:")
                for item in s.get('deposits', []):
                    sym = item['symbol']
                    amt = item['amount']
                    price = prices.get(sym)
                    usd_val = amt * price if price is not None else None
                    if usd_val is not None:
                        total_usd += usd_val
                        print(f"    deposit {sym}: {amt:.8f} (≈ ${usd_val:.2f})")
                    else:
                        print(f"    deposit {sym}: {amt:.8f}")
                for item in s.get('borrows', []):
                    sym = item['symbol']
                    amt = item['amount']
                    price = prices.get(sym)
                    usd_val = amt * price if price is not None else None
                    if usd_val is not None:
                        total_usd -= usd_val
                        print(f"    borrow {sym}: {amt:.8f} (≈ ${usd_val:.2f})")
                    else:
                        print(f"    borrow {sym}: {amt:.8f}")
        if res.get('entries') or res.get('suilend'):
            print(f"  Wallet value (USD): ≈ ${total_usd:.2f}")


if __name__ == '__main__':
    main()
