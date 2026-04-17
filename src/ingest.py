"""Bronze-layer readers for strike datasets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRONZE_DATA_DIR = PROJECT_ROOT / "data" / "bronze"

ATTACKS_FILENAME = "missile_attacks_daily.csv"
WEAPON_REFERENCE_FILENAME = "missiles_and_uavs.csv"


def load_bronze_csv(filename: str) -> pd.DataFrame:
    """Read a bronze-layer CSV file and attach lightweight lineage metadata."""
    path = BRONZE_DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Bronze data file not found: {path}")

    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    frame.insert(0, "source_row_number", range(1, len(frame) + 1))
    frame.insert(0, "source_file", path.name)
    return frame


def load_attacks_raw() -> pd.DataFrame:
    """Load the daily attacks dataset from bronze."""
    return load_bronze_csv(ATTACKS_FILENAME)


def load_weapon_reference_raw() -> pd.DataFrame:
    """Load the missile and UAV reference dataset from bronze."""
    return load_bronze_csv(WEAPON_REFERENCE_FILENAME)
