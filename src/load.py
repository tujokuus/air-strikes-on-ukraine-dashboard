"""Silver- and gold-layer writers for strike datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SILVER_DATA_DIR = PROJECT_ROOT / "data" / "silver"


def write_silver_csv(frame: pd.DataFrame, filename: str) -> Path:
    """Write a silver-layer dataframe as UTF-8 CSV for local inspection."""
    path = SILVER_DATA_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path
