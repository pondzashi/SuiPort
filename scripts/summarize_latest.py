from __future__ import annotations
import json
from pathlib import Path


def fmt_money(x):
    return "-" if x is None else f"{x:,.6f}".rstrip('0').rstrip('.')


def main() -> None:
    p = Path('data/latest.json')
    if not p.exists():
        print("# Portfolio summary

Latest file not found.")
        return

    data = json.loads(p.read_text())

    lines = []
    lines.append("# Portfolio summary")
    lines.append("")
    lines.append(f"**As of:** {data.get('date_iso','-')}  ")
    tot = data.get('totals_usd') or {}
    lines.append(
        f"**Totals (USD):** wallet={fmt_money(tot.get('wallet_sum'))}, "
        f"suilend_net={fmt_money(tot.get('suilend_net'))}, "
        f"**portfolio={fmt_money(tot.get('portfolio_total'))}**"
    )
    lines.append("")

    for acc in data.get('accounts', []):
        addr = acc.get('address','-')
        lines.append(f"## Address {addr}")
        lines.append("")

        # Wallet table (non-zero only)
        nz = [b for b in acc.get('balances', []) if (b.get('human_balance') or 0) > 0]
        if nz:
            lines.append("### Wallet balances")
            lines.append("| Symbol | Balance | USD price | USD value |")
            lines.append("|---|---:|---:|---:|")
            for b in nz:
                lines.append(
                    f"| {b.get('symbol','')} | {fmt_money(b.get('human_balance'))} | "
                    f"{fmt_money(b.get('usd_price'))} | {fmt_money(b.get('usd_value'))} |"
                )
            lines.append("")
            lines.append(f"**Wallet total (USD):** {fmt_money((acc.get('totals') or {}).get('wallet_usd'))}")
            lines.append("")

        # Suilend summary
        ss = (acc.get('defi') or {}).get('suilend_summary') or {}
        items = ss.get('items') or []
        if items:
            lines.append("### Suilend positions")
            lines.append("| Type | Symbol | Amount | USD price | USD value |")
            lines.append("|---|---|---:|---:|---:|")
            for it in items:
                lines.append(
                    f"| {it.get('kind','')} | {it.get('symbol','')} | {fmt_money(it.get('amount'))} | "
                    f"{fmt_money(it.get('usd_price'))} | {fmt_money(it.get('usd_value'))} |"
                )
            lines.append("")
            lines.append(f"**Deposits:** {fmt_money(ss.get('deposits_usd'))}  ")
            lines.append(f"**Borrows:** {fmt_money(ss.get('borrows_usd'))}  ")
            lines.append(f"**Net:** {fmt_money(ss.get('net_usd'))}")
            lines.append("")

    print("
".join(lines))


if __name__ == '__main__':
    main()
