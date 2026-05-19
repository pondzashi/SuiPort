"""Data transformation and normalization utilities."""

from __future__ import annotations

import pandas as pd


REQUIRED_COLUMNS = [
    "asset_name",
    "symbol",
    "balance",
    "value_usd",
]


def _to_float(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.strip()
        .replace({"": None, "None": None, "-": None})
        .astype(float)
    )


def normalize_portfolio_payload(payload: dict) -> pd.DataFrame:
    """Create clean dataframe with canonical fields for dashboard analytics."""
    raw_items = payload.get("items", payload.get("data", []))
    df = pd.DataFrame(raw_items)

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[REQUIRED_COLUMNS].copy()
    df["balance"] = _to_float(df["balance"])
    df["value_usd"] = _to_float(df["value_usd"])

    total_value = df["value_usd"].sum(min_count=1)
    if pd.notna(total_value) and total_value > 0:
        df["portfolio_pct"] = (df["value_usd"] / total_value) * 100
    else:
        df["portfolio_pct"] = 0.0

    df["fetched_at"] = payload.get("_fetched_at")
    df = df.sort_values("value_usd", ascending=False, na_position="last").reset_index(drop=True)
    return df


def compute_kpis(df: pd.DataFrame) -> dict[str, float]:
    return {
        "total_portfolio_usd": float(df["value_usd"].sum(min_count=1) or 0.0),
        "asset_count": int(df["symbol"].nunique(dropna=True)),
    }
