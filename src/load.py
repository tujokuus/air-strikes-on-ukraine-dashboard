"""Silver- and gold-layer writers for strike datasets."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SILVER_DATA_DIR = PROJECT_ROOT / "data" / "silver"


def write_silver_csv(frame: pd.DataFrame, filename: str) -> Path:
    """Write a silver-layer dataframe as UTF-8 CSV for local inspection."""
    path = SILVER_DATA_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def write_silver_duckdb(
    tables: dict[str, pd.DataFrame],
    filename: str = "silver.duckdb",
) -> Path:
    """Write silver-layer dataframes into a local DuckDB file."""
    path = SILVER_DATA_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(path))
    try:
        for table_name, frame in tables.items():
            temp_view_name = f"tmp_{table_name}"
            connection.register(temp_view_name, frame)
            connection.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            connection.execute(
                f'CREATE TABLE "{table_name}" AS SELECT * FROM "{temp_view_name}"'
            )
            connection.unregister(temp_view_name)
    finally:
        connection.close()

    return path
