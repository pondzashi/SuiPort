"""Data access layer for fetching portfolio data from Suivision/Blockvision.

Strategy:
1) Try a documented API first (Blockvision public API product family used by Suivision).
2) Fallback to browser scraping with Playwright when API is unavailable.

This module is intentionally stateless and returns plain Python dictionaries
that can be normalized downstream.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from typing import Any

import requests
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

LOGGER = logging.getLogger(__name__)

# Based on publicly documented Blockvision v2 API family.
BLOCKVISION_DEFI_URL = "https://api.blockvision.org/v2/sui/account/defiPortfolio"


@dataclass
class FetchConfig:
    timeout_seconds: int = 20
    user_agent: str = "SuiPortResearchBot/1.0 (+local analysis)"
    min_request_interval_seconds: float = 1.0


class DataFetchError(RuntimeError):
    """Raised when no data source could provide portfolio data."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((requests.RequestException, ValueError)),
)
def fetch_via_blockvision_api(
    address: str,
    api_key: str,
    protocol: str = "cetus",
    config: FetchConfig | None = None,
) -> dict[str, Any]:
    """Fetch portfolio via Blockvision API (preferred over scraping).

    Parameters
    ----------
    address: Sui address.
    api_key: Blockvision API key.
    protocol: DeFi protocol selector required by endpoint.
    """
    cfg = config or FetchConfig()
    headers = {
        "x-api-key": api_key,
        "User-Agent": cfg.user_agent,
        "Accept": "application/json",
    }
    response = requests.get(
        BLOCKVISION_DEFI_URL,
        params={"address": address, "protocol": protocol},
        headers=headers,
        timeout=cfg.timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    payload["_fetched_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    payload["_source"] = "blockvision_api"
    return payload


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
)
def fetch_via_suivision_scrape(address: str, config: FetchConfig | None = None) -> dict[str, Any]:
    """Fallback scraper that parses server-rendered HTML tokens when possible.

    Notes:
    - For dynamic-only pages, use `fetch_via_suivision_playwright` below.
    - Keep selectors semantic and regex-based to reduce fragility.
    """
    cfg = config or FetchConfig()
    url = f"https://suivision.xyz/account/{address}?tab=Portfolio"

    headers = {"User-Agent": cfg.user_agent}
    res = requests.get(url, headers=headers, timeout=cfg.timeout_seconds)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    page_text = soup.get_text(" ", strip=True)

    # Lightweight extraction fallback: capture token-like rows from textual blocks.
    token_pattern = re.compile(
        r"(?P<name>[A-Za-z0-9 ._-]{2,})\s+\((?P<symbol>[A-Z0-9]{2,12})\)\s+"
        r"(?P<balance>[0-9,]+(?:\.[0-9]+)?)\s+\$?(?P<usd>[0-9,]+(?:\.[0-9]+)?)"
    )

    items: list[dict[str, Any]] = []
    for match in token_pattern.finditer(page_text):
        items.append(
            {
                "asset_name": match.group("name").strip(),
                "symbol": match.group("symbol").strip(),
                "balance": match.group("balance"),
                "value_usd": match.group("usd"),
            }
        )

    if not items:
        raise DataFetchError("No portfolio rows discovered in static HTML; JS rendering likely required.")

    return {
        "_source": "suivision_html_scrape",
        "_fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "address": address,
        "items": items,
    }


def fetch_via_suivision_playwright(address: str) -> dict[str, Any]:
    """JS-rendered fallback using Playwright.

    Requires: `playwright install chromium`
    """
    from playwright.sync_api import sync_playwright

    url = f"https://suivision.xyz/account/{address}?tab=Portfolio"
    records: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60_000)

        # Use role/text-aware selectors instead of brittle CSS hashes.
        rows = page.locator("table tbody tr")
        for i in range(rows.count()):
            cells = rows.nth(i).locator("td")
            if cells.count() < 4:
                continue
            records.append(
                {
                    "asset_name": cells.nth(0).inner_text().strip(),
                    "symbol": cells.nth(1).inner_text().strip(),
                    "balance": cells.nth(2).inner_text().strip(),
                    "value_usd": cells.nth(3).inner_text().strip().replace("$", ""),
                }
            )

        browser.close()

    if not records:
        raise DataFetchError("Playwright could not locate portfolio table rows.")

    return {
        "_source": "suivision_playwright",
        "_fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "address": address,
        "items": records,
    }


def get_portfolio_data(address: str, api_key: str | None = None, protocol: str = "cetus") -> dict[str, Any]:
    """Primary orchestrator: API first, scraping fallback."""
    if api_key:
        try:
            return fetch_via_blockvision_api(address=address, api_key=api_key, protocol=protocol)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Blockvision API fetch failed, falling back to scraping: %s", exc)

    try:
        return fetch_via_suivision_scrape(address)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Static scrape failed, trying Playwright: %s", exc)
        return fetch_via_suivision_playwright(address)
