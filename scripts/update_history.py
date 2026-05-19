"""Append daily snapshot totals into historical datasets for trend analysis."""

from __future__ import annotations

import csv
import json
from pathlib import Path

DATA_DIR = Path("data")
LATEST_JSON = DATA_DIR / "latest.json"
TOTALS_CSV = DATA_DIR / "history_totals.csv"
ASSETS_CSV = DATA_DIR / "history_assets.csv"


def load_latest() -> dict:
    return json.loads(LATEST_JSON.read_text())


def append_unique_row(path: Path, fieldnames: list[str], row: dict[str, object], key_fields: list[str]) -> bool:
    existing_keys: set[tuple[str, ...]] = set()
    if path.exists():
        with path.open(newline="") as f:
            for item in csv.DictReader(f):
                existing_keys.add(tuple(str(item.get(k, "")) for k in key_fields))

    key = tuple(str(row.get(k, "")) for k in key_fields)
    if key in existing_keys:
        return False

    write_header = not path.exists()
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    return True


def main() -> None:
    latest = load_latest()
    date_iso = latest.get("date_iso", "")
    totals = latest.get("totals_usd", {})

    append_unique_row(
        TOTALS_CSV,
        ["date_iso", "wallet_sum", "suilend_net", "portfolio_total"],
        {
            "date_iso": date_iso,
            "wallet_sum": totals.get("wallet_sum", ""),
            "suilend_net": totals.get("suilend_net", ""),
            "portfolio_total": totals.get("portfolio_total", ""),
        },
        ["date_iso"],
    )

    for account in latest.get("accounts", []):
        address = account.get("address", "")
        for bal in account.get("balances", []):
            append_unique_row(
                ASSETS_CSV,
                ["date_iso", "address", "symbol", "coin_type", "human_balance", "usd_value"],
                {
                    "date_iso": date_iso,
                    "address": address,
                    "symbol": bal.get("symbol", ""),
                    "coin_type": bal.get("coin_type", ""),
                    "human_balance": bal.get("human_balance", ""),
                    "usd_value": bal.get("usd_value", ""),
                },
                ["date_iso", "address", "coin_type"],
            )


if __name__ == "__main__":
    main()
