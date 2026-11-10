from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import streamlit as st

from src.release_data import install_latest_release

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLD_DB_PATH = Path(os.environ.get('DASHBOARD_GOLD_DB', PROJECT_ROOT / 'data/gold/gold.duckdb'))


@st.cache_resource(show_spinner=False)
def _bootstrap_gold_database() -> bool:
    # An explicit path is reserved for local development and candidate testing.
    if os.environ.get('DASHBOARD_GOLD_DB'):
        if not GOLD_DB_PATH.is_file():
            raise FileNotFoundError(f'Gold database not found: {GOLD_DB_PATH}')
    else:
        install_latest_release(GOLD_DB_PATH)
    return True


def ensure_gold_database() -> None:
    try:
        _bootstrap_gold_database()
    except Exception as exc:
        st.error('Approved Gold database could not be loaded. '
                 'Please retry later or contact the dashboard maintainer. '
                 f'({type(exc).__name__}: {exc})')
        st.stop()


@st.cache_data(show_spinner=False)
def _query(sql: str, db_mtime_ns: int, params: tuple[Any, ...] | None = None) -> pd.DataFrame:
    ensure_gold_database()
    with duckdb.connect(str(GOLD_DB_PATH), read_only=True) as connection:
        return connection.execute(sql, params or ()).df()


def query(sql: str, params: tuple[Any, ...] | None = None) -> pd.DataFrame:
    ensure_gold_database()
    return _query(sql, GOLD_DB_PATH.stat().st_mtime_ns, params)


def relation_has_column(relation_name: str, column_name: str, schema_name: str = 'main') -> bool:
    result = query('SELECT 1 FROM information_schema.columns WHERE table_schema = ? '
                   'AND table_name = ? AND column_name = ? LIMIT 1',
                   (schema_name, relation_name, column_name))
    return not result.empty


def format_int(value: object) -> str:
    return '0' if pd.isna(value) else f'{int(value):,}'
