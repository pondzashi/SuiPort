"""Fetch DeFi data from Suilend, Cetus, and Aftermath for given Sui addresses.

This is a simple best-effort implementation that queries each protocol's
public API.  Addresses are read from the environment variable
``SUI_ADDRESSES`` (comma-separated) or ``SUI_ADDRESS``.  Results are stored as
JSON files in the ``data`` directory.  Any errors are written to ``*_error.json``
files so downstream tooling can surface failures gracefully.
"""

from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Callable, Dict

import urllib.request
import urllib.error

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
OUT_DIR = pathlib.Path(os.environ.get("OUT_DIR", "data"))
ADDRS_ENV = os.environ.get("SUI_ADDRESSES") or os.environ.get("SUI_ADDRESS") or ""
ADDRESSES = [a.strip() for a in ADDRS_ENV.split(",") if a.strip()]
UA = "sui-portfolio-bot/1.0 (+github-actions)"

# Endpoints for each protocol.  These URLs are based on publicly documented
# APIs.  If an API changes, adjust the URL builders below.
PROTOCOL_ENDPOINTS: Dict[str, Callable[[str], str]] = {
    "suilend": lambda addr: f"https://api.suilend.finance/v1/account/{addr}",
    "cetus": lambda addr: f"https://api.cetus.zone/v1/account/{addr}",
    "aftermath": lambda addr: f"https://api.aftermath.finance/v1/account/{addr}",
}


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def fetch_json(url: str) -> dict:
    """Fetch JSON data from ``url`` using a common User-Agent."""
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": UA},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def write_json(path: pathlib.Path, obj: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))


# ------------------------------------------------------------
# Main logic
# ------------------------------------------------------------
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not ADDRESSES:
        write_json(OUT_DIR / "protocols_error.json", {"error": "no addresses"})
        return

    for addr in ADDRESSES:
        pref = addr[:10]
        for proto, url_fn in PROTOCOL_ENDPOINTS.items():
            url = url_fn(addr)
            try:
                data = fetch_json(url)
                write_json(OUT_DIR / f"{proto}_{pref}.json", data)
            except Exception as e:  # noqa: BLE001 - broad to capture network errors
                write_json(
                    OUT_DIR / f"{proto}_{pref}_error.json",
                    {"error": str(e), "url": url},
                )
            time.sleep(0.25)  # be nice to public APIs


if __name__ == "__main__":
    main()
