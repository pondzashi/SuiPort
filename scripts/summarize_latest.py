from __future__ import annotations
import json
from pathlib import Path
from collections import defaultdict


def fmt_money(x: float | None) -> str:
    return "-" if x is None else f"${x:,.2f}"


def fmt_num(x: float | None) -> str:
    return "-" if x is None else (f"{x:,.6f}".rstrip('0').rstrip('.'))


def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def build_report() -> str:
    data = load_json('data/latest.json')
    if not data:
        return "# Portfolio report Latest file not found."

    date_iso = data.get('date_iso', '-')

    # Totals from latest.json
    totals = data.get('totals_usd') or {}
    wallet_sum = float(totals.get('wallet_sum') or 0)

    # Aggregate Suilend net across accounts
    lending_totals = defaultdict(float)
    per_account_sections: list[str] = []

    for acc in data.get('accounts', []):
        addr = acc.get('address', '-')

        # Wallet table
        wallet_rows = [b for b in acc.get('balances', []) if (b.get('human_balance') or 0) > 0]
        # sort by usd_value desc (unpriced last)
        wallet_rows.sort(key=lambda b: (b.get('usd_value') is None, -(b.get('usd_value') or 0)))
        wallet_total_usd = float((acc.get('totals') or {}).get('wallet_usd') or 0)

        # Suilend summary (already USD)
        ss = (acc.get('defi') or {}).get('suilend_summary') or {}
        suilend_deposits = float(ss.get('deposits_usd') or 0)
        suilend_borrows = float(ss.get('borrows_usd') or 0)
        suilend_net = float(ss.get('net_usd') or 0)
        lending_totals['Suilend'] += suilend_net

        # Account section
        lines = []
        lines.append(f"## Address {addr}")
        lines.append("")
        if wallet_rows:
            lines.append("### Wallet (non-zero)")
            lines.append("| Symbol | Balance | USD price | USD value |")
            lines.append("|---|---:|---:|---:|")
            for b in wallet_rows:
                lines.append(
                    f"| {b.get('symbol','')} | {fmt_num(b.get('human_balance'))} | "
                    f"{fmt_num(b.get('usd_price'))} | {fmt_money(b.get('usd_value'))} |"
                )
            lines.append("")
            lines.append(f"**Wallet total (USD):** {fmt_money(wallet_total_usd)}")
            lines.append("")

        if ss.get('items'):
            lines.append("### Suilend")
            lines.append("| Type | Symbol | Amount | USD price | USD value |")
            lines.append("|---|---|---:|---:|---:|")
            for it in ss['items']:
                lines.append(
                    f"| {it.get('kind','')} | {it.get('symbol','')} | {fmt_num(it.get('amount'))} | "
                    f"{fmt_num(it.get('usd_price'))} | {fmt_money(it.get('usd_value'))} |"
                )
            lines.append("")
            lines.append(f"**Deposits:** {fmt_money(suilend_deposits)}  ")
            lines.append(f"**Borrows:** {fmt_money(suilend_borrows)}  ")
            lines.append(f"**Net:** {fmt_money(suilend_net)}")
            lines.append("")

        # Trailing blank line to keep spacing consistent when joined later
        lines.append("")
        per_account_sections.append("\n".join(lines))

    # Optional: Other protocols (placeholders until fetchers added)
    # If in the future we write data/scallop_*.json, data/navi_*.json, we can parse here.
    scallop_total = 0.0
    navi_total = 0.0
    vaults_aftermath = 0.0
    vaults_cetus = 0.0

    lending_total = lending_totals.get('Suilend', 0.0) + scallop_total + navi_total
    portfolio_total = wallet_sum + lending_total + vaults_aftermath + vaults_cetus

    # Header
    head: list[str] = []
    head.append("# Portfolio report")
    head.append("")
    head.append(f"**As of:** {date_iso}  ")
    head.append(
        f"**Totals (USD):** wallet={fmt_money(wallet_sum)}, "
        f"lending={fmt_money(lending_total)}, vaults={fmt_money(vaults_aftermath + vaults_cetus)}, "
        f"**portfolio={fmt_money(portfolio_total)}**"
    )
    head.append("")

    # Protocol summary like your screenshot
    head.append("## Lending")
    head.append(f"- Suilend — {fmt_money(lending_totals.get('Suilend', 0.0))}")
    head.append(f"- Scallop — {fmt_money(scallop_total)} *(not yet integrated)*")
    head.append(f"- Navi — {fmt_money(navi_total)} *(not yet integrated)*")
    head.append("")
    head.append("## Vaults")
    head.append(f"- Aftermath Finance — {fmt_money(vaults_aftermath)} *(not yet integrated)*")
    head.append(f"- Cetus — {fmt_money(vaults_cetus)} *(not yet integrated)*")
    head.append("")

    sections: list[str] = head + [""] + per_account_sections if per_account_sections else head
    return "\n".join(sections).rstrip() + "\n"


if __name__ == '__main__':
    print(build_report())
