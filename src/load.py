"""Silver- and gold-layer writers for strike datasets."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SILVER_DATA_DIR = PROJECT_ROOT / "data" / "silver"
GOLD_DATA_DIR = PROJECT_ROOT / "data" / "gold"
SQL_DIR = PROJECT_ROOT / "sql"


def write_silver_csv(frame: pd.DataFrame, filename: str) -> Path:
    """Write a silver-layer dataframe as UTF-8 CSV for local inspection."""
    path = SILVER_DATA_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _write_duckdb_tables(path: Path, tables: dict[str, pd.DataFrame]) -> Path:
    """Write dataframes into a DuckDB file as physical tables."""
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


def _split_sql_statements(script: str) -> list[str]:
    """Split a SQL script into executable statements."""
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False

    for char in script:
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote

        if char == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            continue

        current.append(char)

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


def _execute_sql_files(connection: duckdb.DuckDBPyConnection, sql_files: list[Path]) -> None:
    """Execute SQL statements from a list of files against an open DuckDB connection."""
    for sql_file in sql_files:
        script = sql_file.read_text(encoding="utf-8")
        for statement in _split_sql_statements(script):
            connection.execute(statement)


def write_silver_duckdb(
    tables: dict[str, pd.DataFrame],
    filename: str = "silver.duckdb",
) -> Path:
    """Write silver-layer dataframes into a local DuckDB file."""
    return _write_duckdb_tables(SILVER_DATA_DIR / filename, tables)


def write_gold_duckdb(
    silver_tables: dict[str, pd.DataFrame],
    filename: str = "gold.duckdb",
    sql_files: list[Path] | None = None,
) -> Path:
    """Write a gold-layer DuckDB database with silver source tables and dashboard marts/views."""
    path = _write_duckdb_tables(GOLD_DATA_DIR / filename, silver_tables)

    connection = duckdb.connect(str(path))
    try:
        files_to_run = sql_files or [SQL_DIR / "marts.sql", SQL_DIR / "views.sql"]
        _execute_sql_files(connection, files_to_run)
    finally:
        connection.close()

    return path
