from __future__ import annotations
import json
from pathlib import Path

def fmt_money(x):
    return "-" if x is None else f"{x:,.6f}".rstrip('0').rstrip('.')

def main() -> None:
    p = Path('data/latest.json')
    if not p.exists():
        print("Latest file not found")
        return
    data = json.loads(p.read_text())

    print(f"# Portfolio summary
")
    print(f"**As of:** {data.get('date_iso','-')}  ")
    tot = data.get('totals_usd') or {}
    print(f"**Totals (USD):** wallet={fmt_money(tot.get('wallet_sum'))}, suilend_net={fmt_money(tot.get('suilend_net'))}, **portfolio={fmt_money(tot.get('portfolio_total'))}**
")

    for acc in data.get('accounts', []):
        addr = acc.get('address','-')
        print(f"## Address {addr}
")
        # Wallet table (non-zero only)
        nz = [b for b in acc.get('balances', []) if (b.get('human_balance') or 0) > 0]
        if nz:
            print("### Wallet balances")
            print("| Symbol | Balance | USD price | USD value |
|---|---:|---:|---:|")
            for b in nz:
                print(f"| {b.get('symbol','')} | {fmt_money(b.get('human_balance'))} | {fmt_money(b.get('usd_price'))} | {fmt_money(b.get('usd_value'))} |")
            print("
")
            print(f"**Wallet total (USD):** {fmt_money((acc.get('totals') or {}).get('wallet_usd'))}
")

        # Suilend summary
        ss = (acc.get('defi') or {}).get('suilend_summary') or {}
        items = ss.get('items') or []
        if items:
            print("### Suilend positions")
            print("| Type | Symbol | Amount | USD price | USD value |
|---|---|---:|---:|---:|")
            for it in items:
                print(f"| {it.get('kind','')} | {it.get('symbol','')} | {fmt_money(it.get('amount'))} | {fmt_money(it.get('usd_price'))} | {fmt_money(it.get('usd_value'))} |")
            print("
")
            print(f"**Deposits:** {fmt_money(ss.get('deposits_usd'))}  ")
            print(f"**Borrows:** {fmt_money(ss.get('borrows_usd'))}  ")
            print(f"**Net:** {fmt_money(ss.get('net_usd'))}
")

if __name__ == '__main__':
    main()

