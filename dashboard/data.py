from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import streamlit as st


# Resolve paths from the repository root so the dashboard works from any launch directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLD_DB_PATH = PROJECT_ROOT / "data" / "gold" / "gold.duckdb"
BRONZE_DATA_DIR = PROJECT_ROOT / "data" / "bronze"
REQUIRED_BRONZE_FILES = [
    BRONZE_DATA_DIR / "missile_attacks_daily.csv",
    BRONZE_DATA_DIR / "missiles_and_uavs.csv",
]


def _copy_streamlit_secret_to_env(name: str) -> None:
    """Expose a root-level Streamlit secret as an environment variable when needed."""
    if os.environ.get(name):
        return

    try:
        value = st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        value = None

    if value:
        os.environ[name] = str(value)


def _bronze_files_exist() -> bool:
    """Return True when the expected source CSV files are already available."""
    return all(path.exists() for path in REQUIRED_BRONZE_FILES)


@st.cache_resource(show_spinner=False)
def _bootstrap_gold_database() -> bool:
    """Build the local gold database for Streamlit Cloud or a fresh local checkout."""
    if not _bronze_files_exist():
        _copy_streamlit_secret_to_env("KAGGLE_API_TOKEN")

        from src.download_data import main as download_data

        download_data()

    from src.pipeline import main as run_pipeline

    run_pipeline()
    return GOLD_DB_PATH.exists()


def ensure_gold_database() -> None:
    """Create or validate the gold database before dashboard queries run."""
    if GOLD_DB_PATH.exists():
        return

    with st.spinner("Gold database not found. Downloading data and building DuckDB marts..."):
        try:
            bootstrapped = _bootstrap_gold_database()
        except SystemExit as exc:
            st.error(
                "Gold database was not found and automatic data bootstrap failed.\n\n"
                f"{exc}\n\n"
                "Local fix: run `poetry run download-data` and `poetry run pipeline`.\n\n"
                "Streamlit Cloud fix: add `KAGGLE_API_TOKEN` to the app secrets."
            )
            st.stop()
        except Exception as exc:
            st.error(
                "Gold database was not found and automatic data bootstrap failed.\n\n"
                f"{type(exc).__name__}: {exc}\n\n"
                "Local fix: run `poetry run download-data` and `poetry run pipeline`.\n\n"
                "Streamlit Cloud fix: add `KAGGLE_API_TOKEN` to the app secrets."
            )
            st.stop()

    if not bootstrapped:
        st.error(
            "Gold database bootstrap finished, but `data/gold/gold.duckdb` was not created."
        )
        st.stop()


@st.cache_data(show_spinner=False)
def _query(sql: str, db_mtime_ns: int, params: tuple[Any, ...] | None = None) -> pd.DataFrame:
    """Run a read-only DuckDB query and return the result as a pandas DataFrame."""
    ensure_gold_database()

    # Open a short-lived read-only connection so Streamlit reruns do not keep the database locked.
    connection = duckdb.connect(str(GOLD_DB_PATH), read_only=True)
    try:
        if params:
            return connection.execute(sql, params).df()
        return connection.execute(sql).df()
    finally:
        connection.close()


def query(sql: str, params: tuple[Any, ...] | None = None) -> pd.DataFrame:
    """Run a cached read-only query that refreshes automatically when gold.duckdb changes."""
    ensure_gold_database()
    return _query(sql, GOLD_DB_PATH.stat().st_mtime_ns, params)


def format_int(value: object) -> str:
    """Format nullable numeric values for Streamlit metric cards."""
    if pd.isna(value):
        return "0"
    return f"{int(value):,}"
