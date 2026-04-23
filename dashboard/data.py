from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st


# Resolve paths from the repository root so the dashboard works from any launch directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLD_DB_PATH = PROJECT_ROOT / "data" / "gold" / "gold.duckdb"


def ensure_gold_database() -> None:
    """Stop the Streamlit app if the gold database has not been generated."""
    if not GOLD_DB_PATH.exists():
        st.error(
            "Gold database was not found. Run `poetry run pipeline` before starting the dashboard."
        )
        st.stop()


@st.cache_data(show_spinner=False)
def _query(sql: str, db_mtime_ns: int) -> pd.DataFrame:
    """Run a read-only DuckDB query and return the result as a pandas DataFrame."""
    ensure_gold_database()

    # Open a short-lived read-only connection so Streamlit reruns do not keep the database locked.
    connection = duckdb.connect(str(GOLD_DB_PATH), read_only=True)
    try:
        return connection.execute(sql).df()
    finally:
        connection.close()


def query(sql: str) -> pd.DataFrame:
    """Run a cached read-only query that refreshes automatically when gold.duckdb changes."""
    ensure_gold_database()
    return _query(sql, GOLD_DB_PATH.stat().st_mtime_ns)


def format_int(value: object) -> str:
    """Format nullable numeric values for Streamlit metric cards."""
    if pd.isna(value):
        return "0"
    return f"{int(value):,}"
