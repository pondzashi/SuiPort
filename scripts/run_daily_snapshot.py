"""Utility entry point to refresh the latest portfolio snapshot and summary."""

from __future__ import annotations

from pathlib import Path

import sui_daily_portfolio
import summarize_latest


def main() -> None:
    """Generate raw data and the Markdown summary for the latest snapshot."""

    # Refresh on-chain data and write data/latest.json plus per-address CSVs.
    sui_daily_portfolio.main()

    # Build the Markdown report and save it alongside the other data files.
    report = summarize_latest.build_report()
    Path("data/latest_report.md").write_text(report)


if __name__ == "__main__":
    main()
