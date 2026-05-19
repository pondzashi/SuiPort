"""Streamlit dashboard for Suivision portfolio monitoring."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from data_fetching import get_portfolio_data
from data_processing import compute_kpis, normalize_portfolio_payload

st.set_page_config(page_title="Sui Portfolio Dashboard", layout="wide")
st.title("Sui Portfolio Dashboard")


def load_history_totals(path: Path = Path("data/history_totals.csv")) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["date_iso", "portfolio_total", "wallet_sum", "suilend_net"])
    hist = pd.read_csv(path)
    if "date_iso" in hist.columns:
        hist["date_iso"] = pd.to_datetime(hist["date_iso"], errors="coerce", utc=True)
    for col in ["portfolio_total", "wallet_sum", "suilend_net"]:
        if col in hist.columns:
            hist[col] = pd.to_numeric(hist[col], errors="coerce")
    return hist.sort_values("date_iso")

with st.sidebar:
    st.header("Configuration")
    address = st.text_input(
        "Sui address",
        value="0xeecf66310b9b8fcf3ab62955a9c2849378d297e9e73954ad0760d80cdd985721",
    )
    protocol = st.selectbox("Protocol (API mode)", ["cetus", "navi"], index=0)
    api_key = st.text_input("Blockvision API key (optional)", type="password", value=os.getenv("BLOCKVISION_API_KEY", ""))
    refresh = st.button("Fetch / Refresh")

if refresh or "portfolio_df" not in st.session_state:
    with st.spinner("Fetching portfolio data..."):
        payload = get_portfolio_data(address=address, api_key=api_key or None, protocol=protocol)
        st.session_state["portfolio_df"] = normalize_portfolio_payload(payload)

if "portfolio_df" in st.session_state:
    df = st.session_state["portfolio_df"]
    kpis = compute_kpis(df)

    k1, k2 = st.columns(2)
    k1.metric("Total Portfolio Value (USD)", f"${kpis['total_portfolio_usd']:,.2f}")
    k2.metric("Distinct Assets", f"{kpis['asset_count']}")

    c1, c2 = st.columns([1, 1])

    with c1:
        st.subheader("Allocation")
        fig = px.treemap(
            df.dropna(subset=["value_usd", "symbol"]),
            path=["symbol"],
            values="value_usd",
            color="portfolio_pct",
            color_continuous_scale="Blues",
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Portfolio Table")
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "value_usd": st.column_config.NumberColumn("Value (USD)", format="$%.2f"),
                "portfolio_pct": st.column_config.NumberColumn("Portfolio %", format="%.2f%%"),
            },
        )

    st.caption("Tip: click column headers in the table to sort; use Streamlit table search/filter controls.")

    hist = load_history_totals()
    if not hist.empty:
        st.subheader("Portfolio Trend (Historical)")
        trend_fig = px.line(hist, x="date_iso", y=["portfolio_total", "wallet_sum", "suilend_net"], markers=True)
        trend_fig.update_layout(legend_title_text="Series", yaxis_title="USD")
        st.plotly_chart(trend_fig, use_container_width=True)
else:
    st.info("Enter settings and click Fetch / Refresh.")
