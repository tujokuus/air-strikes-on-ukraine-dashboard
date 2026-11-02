"""Fixtures for running tests without touching the project's real data."""

from pathlib import Path
from shutil import copy2

import pytest

import src.ingest as ingest
import src.load as load


@pytest.fixture
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect pipeline input and output paths to a temporary directory."""
    bronze = tmp_path / "bronze"
    bronze.mkdir()
    fixtures = Path(__file__).parent / "fixtures"
    for name in (ingest.ATTACKS_FILENAME, ingest.WEAPON_REFERENCE_FILENAME):
        copy2(fixtures / name, bronze / name)

    monkeypatch.setattr(ingest, "BRONZE_DATA_DIR", bronze)
    monkeypatch.setattr(load, "SILVER_DATA_DIR", tmp_path / "silver")
    monkeypatch.setattr(load, "GOLD_DATA_DIR", tmp_path / "gold")
    return tmp_path
