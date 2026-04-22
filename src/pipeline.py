"""Run the lightweight bronze-to-silver pipeline for the project."""

from __future__ import annotations

import duckdb

from .ingest import load_attacks_raw, load_weapon_reference_raw
from .load import write_gold_duckdb, write_silver_csv, write_silver_duckdb
from .transform import transform_attacks, transform_weapon_reference


def main() -> None:
    raw_attacks = load_attacks_raw()
    raw_reference = load_weapon_reference_raw()

    weapon_reference = transform_weapon_reference(raw_reference)
    attacks_clean, attacks_regions = transform_attacks(
        raw_attacks=raw_attacks,
        weapon_reference=weapon_reference,
    )

    reference_path = write_silver_csv(weapon_reference, "weapon_reference_clean.csv")
    attacks_path = write_silver_csv(attacks_clean, "attacks_clean.csv")
    regions_path = write_silver_csv(attacks_regions, "attacks_regions.csv")
    silver_tables = {
        "silver_weapon_reference": weapon_reference,
        "silver_attacks": attacks_clean,
        "silver_attack_regions": attacks_regions,
    }

    silver_db_path = None
    try:
        silver_db_path = write_silver_duckdb(silver_tables)
    except duckdb.IOException as exc:
        print(f"Warning: could not refresh silver DuckDB file: {exc}")

    gold_db_path = write_gold_duckdb(
        silver_tables
    )

    print(f"Wrote weapon reference rows: {len(weapon_reference):,} -> {reference_path}")
    print(f"Wrote clean attack rows:     {len(attacks_clean):,} -> {attacks_path}")
    print(f"Wrote exploded area rows:    {len(attacks_regions):,} -> {regions_path}")
    if silver_db_path is not None:
        print(f"Wrote silver DuckDB tables:  {silver_db_path}")
    print(f"Wrote gold DuckDB marts:     {gold_db_path}")
    print(
        "Reference matches in attacks: "
        f"{int(attacks_clean['weapon_reference_match'].sum()):,}/{len(attacks_clean):,}"
    )


if __name__ == "__main__":
    main()
