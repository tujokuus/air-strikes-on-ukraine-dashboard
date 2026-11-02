"""Check meaningful transformations using synthetic source data."""

import pandas as pd

from src.ingest import load_attacks_raw, load_weapon_reference_raw
from src.transform import transform_attacks, transform_weapon_reference


def test_attack_dates_regions_and_reference_are_normalized(isolated_data_dir):
    attacks = load_attacks_raw()
    attacks.loc[0, "model"] = "  EXAMPLE UAV  "
    attacks.loc[0, "target"] = "kyiv oblast and ODESA oblast and Kyiv oblast"
    reference = transform_weapon_reference(load_weapon_reference_raw())

    clean, regions = transform_attacks(attacks, reference)

    assert clean.loc[0, "event_date"] == "2025-01-01"
    assert clean.loc[0, "weapon_model_key"] == "example uav"
    assert bool(clean.loc[0, "weapon_reference_match"])
    assert clean.loc[0, "weapon_category"] == "UAV"
    assert clean.loc[0, "launched"] == 10
    assert clean.loc[0, "area_count"] == 2
    assert regions.loc[regions["source_row_number"] == 1, "area_region"].tolist() == [
        "Kyiv oblast", "Odesa oblast"
    ]


def test_missing_optional_numeric_column_is_preserved_as_null(isolated_data_dir):
    attacks = load_attacks_raw().drop(columns=["not_reach_goal"])
    reference = transform_weapon_reference(load_weapon_reference_raw())

    clean, _ = transform_attacks(attacks, reference)

    assert "not_reach_goal" in clean.columns
    assert clean["not_reach_goal"].isna().all()
    assert pd.api.types.is_integer_dtype(clean["not_reach_goal"].dtype)
