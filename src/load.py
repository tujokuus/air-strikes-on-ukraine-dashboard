"""Output writers for processed strike datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"


def write_processed_csv(frame: pd.DataFrame, filename: str) -> Path:
    """Write a processed dataframe as UTF-8 CSV for local inspection."""
    path = PROCESSED_DATA_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path
