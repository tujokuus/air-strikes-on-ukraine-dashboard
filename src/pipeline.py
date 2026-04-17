"""Run the lightweight CSV-to-processed pipeline for the project."""

from __future__ import annotations

from .ingest import load_attacks_raw, load_weapon_reference_raw
from .load import write_processed_csv
from .transform import transform_attacks, transform_weapon_reference


def main() -> None:
    raw_attacks = load_attacks_raw()
    raw_reference = load_weapon_reference_raw()

    weapon_reference = transform_weapon_reference(raw_reference)
    attacks_clean, attacks_regions = transform_attacks(
        raw_attacks=raw_attacks,
        weapon_reference=weapon_reference,
    )

    reference_path = write_processed_csv(weapon_reference, "weapon_reference_clean.csv")
    attacks_path = write_processed_csv(attacks_clean, "attacks_clean.csv")
    regions_path = write_processed_csv(attacks_regions, "attacks_regions.csv")

    print(f"Wrote weapon reference rows: {len(weapon_reference):,} -> {reference_path}")
    print(f"Wrote clean attack rows:     {len(attacks_clean):,} -> {attacks_path}")
    print(f"Wrote exploded area rows:    {len(attacks_regions):,} -> {regions_path}")
    print(
        "Reference matches in attacks: "
        f"{int(attacks_clean['weapon_reference_match'].sum()):,}/{len(attacks_clean):,}"
    )


if __name__ == "__main__":
    main()
