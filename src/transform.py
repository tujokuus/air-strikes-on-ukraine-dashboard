"""Transform bronze strike datasets into analytics-ready silver tables."""

from __future__ import annotations

import json
import re
from typing import Iterable

import pandas as pd


AREA_CANONICAL_MAP = {
    "odesa oblast": "Odesa oblast",
    "mykolaiv oblast": "Mykolaiv oblast",
    "kyiv oblast": "Kyiv oblast",
    "lviv oblast": "Lviv oblast",
    "rivne oblast": "Rivne oblast",
    "volyn oblast": "Volyn oblast",
    "kherson oblast": "Kherson oblast",
    "khmelnytskyi oblast": "Khmelnytskyi oblast",
    "poltava oblast": "Poltava oblast",
    "kharkiv oblast": "Kharkiv oblast",
    "sumy oblast": "Sumy oblast",
    "chernihiv oblast": "Chernihiv oblast",
    "zaporizhzhia oblast": "Zaporizhzhia oblast",
    "dnipropetrovsk oblast": "Dnipropetrovsk oblast",
    "donetsk oblast": "Donetsk oblast",
    "kirovohrad oblast": "Kirovohrad oblast",
    "vinnytsia oblast": "Vinnytsia oblast",
    "cherkasy oblast": "Cherkasy oblast",
    "kursk oblast": "Kursk oblast",
    "kyiv": "Kyiv",
    "odesa": "Odesa",
    "kharkiv": "Kharkiv",
    "kherson": "Kherson",
    "dnipro": "Dnipro",
    "zaporizhzhia": "Zaporizhzhia",
    "sumy": "Sumy",
    "kramatorsk": "Kramatorsk",
    "kryvyi rih": "Kryvyi Rih",
    "starokostiantyniv": "Starokostiantyniv",
    "kolomyia": "Kolomyia",
    "ochakiv": "Ochakiv",
    "snake island": "Snake Island",
    "ukraine": None,
    "south": None,
    "north": None,
    "east": None,
    "west": None,
    "center": None,
    "centre": None,
    "north and center": None,
    "south and east": None,
    "south and north": None,
    "north and east": None,
    "south and east and center": None,
    "south and north and center": None,
    "south-east": None,
    "north-east": None,
    "front line": None,
    "odesa oblast, black sea": "Odesa oblast",
    "kyiv oblast (south)": "Kyiv oblast",
}

AREA_MACRO_MAP = {
    "ukraine": "nationwide",
    "snake island": "south",
    "south": "south",
    "south-east": "south-east",
    "north-east": "north-east",
    "south and east": "south-east",
    "south and north": "multi",
    "north": "north",
    "east": "east",
    "west": "west",
    "center": "center",
    "centre": "center",
    "north and center": "multi",
    "north and east": "multi",
    "south and east and center": "multi",
    "south and north and center": "multi",
    "front line": "front line",
    "odesa oblast": "south",
    "mykolaiv oblast": "south",
    "kherson oblast": "south",
    "zaporizhzhia oblast": "south-east",
    "zaporizhzhia": "south-east",
    "dnipropetrovsk oblast": "center-east",
    "dnipro": "center-east",
    "kryvyi rih": "center-east",
    "kirovohrad oblast": "center",
    "cherkasy oblast": "center",
    "vinnytsia oblast": "center-west",
    "poltava oblast": "center-east",
    "kharkiv oblast": "east",
    "kharkiv": "east",
    "donetsk oblast": "east",
    "sumy oblast": "north-east",
    "sumy": "north-east",
    "chernihiv oblast": "north",
    "kyiv oblast": "north",
    "kyiv": "north",
    "lviv oblast": "west",
    "rivne oblast": "west",
    "volyn oblast": "west",
    "khmelnytskyi oblast": "center-west",
    "starokostiantyniv": "center-west",
    "kolomyia": "west",
    "ochakiv": "south",
    "odesa": "south",
    "kherson": "south",
    "kramatorsk": "east",
    "kursk oblast": "international",
}

ATTACK_NUMERIC_COLUMNS = [
    "launched",
    "destroyed",
    "not_reach_goal",
    "still_attacking",
    "is_shahed",
    "num_hit_location",
    "num_fall_fragment_location",
    "carrier",
    "turbojet",
    "turbojet_destroyed",
]

AREA_SPLIT_PATTERN = re.compile(r"\s+and\s+", flags=re.IGNORECASE)
MULTISPACE_PATTERN = re.compile(r"\s+")
RAION_PATTERN = re.compile(r"^(?P<oblast>.+? oblast),\s+.+?\s+raion$", flags=re.IGNORECASE)
SNAKE_CASE_PATTERN = re.compile(r"[^0-9a-zA-Z]+")


def _snake_case(name: str) -> str:
    snake = SNAKE_CASE_PATTERN.sub("_", name.strip()).strip("_").lower()
    return snake.replace("name_nato", "name_nato").replace("in_sevice", "in_service")


def _normalize_string(value: object) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return MULTISPACE_PATTERN.sub(" ", str(value).strip())


def _strip_object_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    object_columns = result.select_dtypes(include="object").columns
    for column in object_columns:
        result[column] = result[column].map(_normalize_string)
    return result


def _normalize_model_key(value: object) -> str:
    return _normalize_string(value).casefold()


def _resolve_area_token(raw_token: str) -> str:
    clean_token = _normalize_string(raw_token)
    if not clean_token:
        return ""

    token_key = clean_token.casefold()
    if token_key in AREA_CANONICAL_MAP:
        return AREA_CANONICAL_MAP[token_key] or ""

    raion_match = RAION_PATTERN.match(token_key)
    if raion_match:
        oblast_key = raion_match.group("oblast").strip()
        if oblast_key in AREA_CANONICAL_MAP:
            return AREA_CANONICAL_MAP[oblast_key] or ""
        return oblast_key.title()

    return clean_token.title()


def split_area_targets(raw_target: object) -> list[str]:
    """Split the raw target field into canonical regions or cities."""
    clean_target = _normalize_string(raw_target)
    if not clean_target:
        return []

    regions: list[str] = []
    seen: set[str] = set()
    for part in AREA_SPLIT_PATTERN.split(clean_target):
        resolved = _resolve_area_token(part)
        if not resolved or resolved in seen:
            continue
        seen.add(resolved)
        regions.append(resolved)
    return regions


def get_area_macro(raw_target: object) -> str:
    """Collapse the target field into a macro-area bucket."""
    clean_target = _normalize_string(raw_target)
    if not clean_target:
        return "unknown"

    macros: set[str] = set()
    for part in AREA_SPLIT_PATTERN.split(clean_target):
        token_key = _normalize_string(part).casefold()
        if token_key in AREA_MACRO_MAP:
            macros.add(AREA_MACRO_MAP[token_key])
            continue

        resolved = _resolve_area_token(part)
        if resolved:
            resolved_key = resolved.casefold()
            if resolved_key in AREA_MACRO_MAP:
                macros.add(AREA_MACRO_MAP[resolved_key])

    if not macros:
        return "unknown"
    if len(macros) == 1:
        return next(iter(macros))
    return "multi"


def _to_nullable_numeric(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series.replace("", pd.NA), errors="coerce")
    if numeric.dropna().empty:
        return numeric.astype("Int64")

    if (numeric.dropna() % 1 == 0).all():
        return numeric.astype("Int64")
    return numeric


def _json_list(values: Iterable[str]) -> str:
    return json.dumps(list(values), ensure_ascii=False)


def _derive_event_date(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series.replace("", pd.NA), errors="coerce")
    event_date = parsed.dt.strftime("%Y-%m-%d")

    fallback_mask = event_date.isna() & series.fillna("").str.match(r"^\d{4}-\d{2}-\d{2}$")
    event_date = event_date.where(~fallback_mask, series.str.slice(0, 10))
    return event_date.fillna("")


def transform_weapon_reference(raw_reference: pd.DataFrame) -> pd.DataFrame:
    """Clean the missile/UAV reference table for later enrichment."""
    reference = raw_reference.copy()
    reference.columns = [_snake_case(column) for column in reference.columns]
    reference = _strip_object_columns(reference)
    reference = reference.rename(
        columns={
            "model": "weapon_model",
            "category": "weapon_category",
            "type": "weapon_type",
            "national_origin": "weapon_national_origin",
        }
    )
    reference["weapon_model_key"] = reference["weapon_model"].map(_normalize_model_key)

    column_order = [
        "source_file",
        "source_row_number",
        "weapon_model",
        "weapon_model_key",
        "weapon_category",
        "weapon_type",
        "weapon_national_origin",
        "launch_platform",
        "name",
        "name_nato",
        "in_service",
        "designer",
        "manufacturer",
        "guidance_system",
        "unit_cost",
    ]
    return reference[column_order]


def transform_attacks(
    raw_attacks: pd.DataFrame,
    weapon_reference: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean the attacks table and produce both row-level and exploded outputs."""
    attacks = raw_attacks.copy()
    attacks.columns = [_snake_case(column) for column in attacks.columns]
    attacks = _strip_object_columns(attacks)
    attacks = attacks.rename(columns={"model": "weapon_model"})
    attacks["weapon_model_key"] = attacks["weapon_model"].map(_normalize_model_key)
    attacks["event_date"] = _derive_event_date(attacks["time_start"])

    for column in ATTACK_NUMERIC_COLUMNS:
        attacks[column] = _to_nullable_numeric(attacks[column])

    attacks["area_regions_list"] = attacks["target"].map(split_area_targets)
    attacks["area_macro"] = attacks["target"].map(get_area_macro)
    attacks["area_count"] = attacks["area_regions_list"].map(len).astype("Int64")
    attacks["area_regions"] = attacks["area_regions_list"].map(_json_list)

    if weapon_reference is not None:
        reference_lookup = (
            weapon_reference[
                [
                    "weapon_model_key",
                    "weapon_category",
                    "weapon_type",
                    "weapon_national_origin",
                ]
            ]
            .drop_duplicates(subset=["weapon_model_key"])
        )
        attacks = attacks.merge(reference_lookup, on="weapon_model_key", how="left")
        attacks["weapon_reference_match"] = attacks["weapon_category"].notna()
    else:
        attacks["weapon_reference_match"] = False

    exploded = attacks.copy()
    exploded["area_region"] = exploded["area_regions_list"].map(lambda values: values if values else [""])
    exploded = exploded.explode("area_region", ignore_index=True)
    exploded["has_specific_area_region"] = exploded["area_region"].ne("")

    base_columns = [
        "source_file",
        "source_row_number",
        "event_date",
        "time_start",
        "time_end",
        "weapon_model",
        "weapon_model_key",
        "weapon_category",
        "weapon_type",
        "weapon_national_origin",
        "weapon_reference_match",
        "launch_place",
        "target",
        "target_main",
        "area_macro",
        "area_count",
        "area_regions",
        "launched",
        "destroyed",
        "not_reach_goal",
        "still_attacking",
        "border_crossing",
        "is_shahed",
        "num_hit_location",
        "num_fall_fragment_location",
        "carrier",
        "turbojet",
        "turbojet_destroyed",
        "affected_region",
        "destroyed_details",
        "launched_details",
        "launch_place_details",
        "source",
    ]

    attacks_clean = attacks[base_columns].copy()
    attacks_regions = exploded[base_columns + ["area_region", "has_specific_area_region"]].copy()

    for frame in (attacks_clean, attacks_regions):
        object_columns = frame.select_dtypes(include="object").columns
        frame[object_columns] = frame[object_columns].fillna("")

    return attacks_clean, attacks_regions
