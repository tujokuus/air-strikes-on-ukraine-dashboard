from __future__ import annotations

from datetime import date

import pandas as pd

from dashboard.data import query


REGION_MACRO_CASE = """
CASE reporting_region
    WHEN 'Odesa oblast' THEN 'south'
    WHEN 'Mykolaiv oblast' THEN 'south'
    WHEN 'Kyiv oblast' THEN 'north'
    WHEN 'Lviv oblast' THEN 'west'
    WHEN 'Rivne oblast' THEN 'west'
    WHEN 'Volyn oblast' THEN 'west'
    WHEN 'Kherson oblast' THEN 'south'
    WHEN 'Khmelnytskyi oblast' THEN 'center-west'
    WHEN 'Poltava oblast' THEN 'center-east'
    WHEN 'Kharkiv oblast' THEN 'east'
    WHEN 'Sumy oblast' THEN 'north-east'
    WHEN 'Chernihiv oblast' THEN 'north'
    WHEN 'Zaporizhzhia oblast' THEN 'south-east'
    WHEN 'Dnipropetrovsk oblast' THEN 'center-east'
    WHEN 'Donetsk oblast' THEN 'east'
    WHEN 'Kirovohrad oblast' THEN 'center'
    WHEN 'Vinnytsia oblast' THEN 'center-west'
    WHEN 'Cherkasy oblast' THEN 'center'
    WHEN 'Ivano-Frankivsk oblast' THEN 'west'
    WHEN 'Kursk oblast' THEN 'international'
    ELSE 'unknown'
END
"""


def get_filtered_overview(start_date: date, end_date: date) -> pd.Series:
    """Return overview metrics for the selected global date range."""
    return query(
        """
        WITH filtered_daily AS (
            SELECT *
            FROM vw_dashboard_daily_activity
            WHERE event_date BETWEEN ? AND ?
        ),
        filtered_models_raw AS (
            SELECT *
            FROM vw_dashboard_weapon_models_daily
            WHERE event_date BETWEEN ? AND ?
        ),
        filtered_models AS (
            SELECT
                weapon_model_key,
                weapon_model,
                CASE
                    WHEN COUNT(DISTINCT weapon_category) = 1 THEN MIN(weapon_category)
                    ELSE 'Mixed'
                END AS weapon_category,
                SUM(attack_rows) AS attack_rows,
                SUM(launched_total) AS launched_total
            FROM filtered_models_raw
            GROUP BY 1, 2
        ),
        overview AS (
            SELECT
                MIN(event_date) AS first_event_date,
                MAX(event_date) AS last_event_date,
                COALESCE(SUM(attack_rows), 0) AS total_attack_rows,
                COUNT(DISTINCT event_date) AS distinct_event_dates,
                COALESCE((SELECT COUNT(DISTINCT weapon_model_key) FROM filtered_models), 0) AS distinct_weapon_models,
                COALESCE((SELECT COUNT(DISTINCT weapon_category) FROM filtered_models), 0) AS distinct_weapon_categories,
                COALESCE(SUM(launched_total), 0) AS total_launched,
                COALESCE(SUM(destroyed_total), 0) AS total_destroyed,
                COALESCE(SUM(not_reach_goal_total), 0) AS total_not_reach_goal,
                COALESCE(SUM(still_attacking_total), 0) AS total_still_attacking
            FROM filtered_daily
        ),
        top_uav AS (
            SELECT
                weapon_model_key AS top_uav_weapon_model_key,
                launched_total AS top_uav_launched
            FROM filtered_models
            WHERE LOWER(weapon_category) = 'uav'
            ORDER BY launched_total DESC, weapon_model_key
            LIMIT 1
        ),
        top_cruise_missile AS (
            SELECT
                weapon_model_key AS top_cruise_missile_weapon_model_key,
                launched_total AS top_cruise_missile_launched
            FROM filtered_models
            WHERE LOWER(weapon_category) = 'cruise missile'
            ORDER BY launched_total DESC, weapon_model_key
            LIMIT 1
        ),
        top_ballistic_missile AS (
            SELECT
                weapon_model_key AS top_ballistic_missile_weapon_model_key,
                launched_total AS top_ballistic_missile_launched
            FROM filtered_models
            WHERE LOWER(weapon_category) LIKE '%ballistic%'
            ORDER BY launched_total DESC, weapon_model_key
            LIMIT 1
        )
        SELECT
            overview.*,
            COALESCE(top_uav.top_uav_weapon_model_key, '-') AS top_uav_weapon_model_key,
            COALESCE(top_uav.top_uav_launched, 0) AS top_uav_launched,
            COALESCE(top_cruise_missile.top_cruise_missile_weapon_model_key, '-') AS top_cruise_missile_weapon_model_key,
            COALESCE(top_cruise_missile.top_cruise_missile_launched, 0) AS top_cruise_missile_launched,
            COALESCE(top_ballistic_missile.top_ballistic_missile_weapon_model_key, '-') AS top_ballistic_missile_weapon_model_key,
            COALESCE(top_ballistic_missile.top_ballistic_missile_launched, 0) AS top_ballistic_missile_launched
        FROM overview
        LEFT JOIN top_uav ON TRUE
        LEFT JOIN top_cruise_missile ON TRUE
        LEFT JOIN top_ballistic_missile ON TRUE
        """,
        (start_date, end_date, start_date, end_date),
    ).iloc[0]


def get_filtered_daily_activity(start_date: date, end_date: date) -> pd.DataFrame:
    """Return daily activity rows for the selected global date range."""
    return query(
        """
        SELECT *
        FROM vw_dashboard_daily_activity
        WHERE event_date BETWEEN ? AND ?
        ORDER BY event_date
        """,
        (start_date, end_date),
    )


def get_filtered_weapon_models(start_date: date, end_date: date) -> pd.DataFrame:
    """Aggregate weapon model metrics over the selected date range."""
    return query(
        """
        WITH aggregated AS (
            SELECT
                weapon_model_key,
                weapon_model,
                CASE
                    WHEN COUNT(DISTINCT weapon_category) = 1 THEN MIN(weapon_category)
                    ELSE 'Mixed'
                END AS weapon_category,
                CASE
                    WHEN COUNT(DISTINCT weapon_type) = 1 THEN MIN(weapon_type)
                    ELSE 'Mixed/Various'
                END AS weapon_type,
                SUM(active_days) AS active_days,
                SUM(attack_rows) AS attack_rows,
                SUM(launched_total) AS launched_total,
                SUM(destroyed_total) AS destroyed_total,
                SUM(matched_rows) AS matched_rows,
                SUM(unmatched_rows) AS unmatched_rows,
                MIN(event_date) AS first_seen,
                MAX(event_date) AS last_seen
            FROM vw_dashboard_weapon_models_daily
            WHERE event_date BETWEEN ? AND ?
            GROUP BY 1, 2
        )
        SELECT
            weapon_model_key,
            weapon_model,
            weapon_category,
            weapon_type,
            active_days,
            attack_rows,
            launched_total,
            destroyed_total,
            matched_rows,
            unmatched_rows,
            ROUND(100.0 * matched_rows / NULLIF(attack_rows, 0), 2) AS reference_coverage_pct,
            ROUND(100.0 * launched_total / NULLIF(SUM(launched_total) OVER (), 0), 2) AS launched_share_pct,
            ROUND(100.0 * destroyed_total / NULLIF(launched_total, 0), 2) AS destroyed_to_launched_pct,
            first_seen,
            last_seen
        FROM aggregated
        ORDER BY launched_total DESC, attack_rows DESC, weapon_model
        """,
        (start_date, end_date),
    )


def get_filtered_weapon_types(start_date: date, end_date: date) -> pd.DataFrame:
    """Aggregate weapon type metrics over the selected date range."""
    return query(
        """
        WITH aggregated AS (
            SELECT
                weapon_category,
                weapon_type,
                SUM(active_days) AS active_days,
                SUM(attack_rows) AS attack_rows,
                SUM(launched_total) AS launched_total,
                SUM(destroyed_total) AS destroyed_total,
                SUM(matched_rows) AS matched_rows,
                SUM(unmatched_rows) AS unmatched_rows
            FROM vw_dashboard_weapon_types_daily
            WHERE event_date BETWEEN ? AND ?
            GROUP BY 1, 2
        )
        SELECT
            weapon_category,
            weapon_type,
            active_days,
            attack_rows,
            launched_total,
            destroyed_total,
            matched_rows,
            unmatched_rows,
            ROUND(100.0 * matched_rows / NULLIF(attack_rows, 0), 2) AS reference_coverage_pct,
            ROUND(100.0 * launched_total / NULLIF(SUM(launched_total) OVER (), 0), 2) AS launched_share_pct,
            ROUND(100.0 * destroyed_total / NULLIF(launched_total, 0), 2) AS destroyed_to_launched_pct
        FROM aggregated
        ORDER BY launched_total DESC, attack_rows DESC, weapon_category, weapon_type
        """,
        (start_date, end_date),
    )


def get_filtered_area_macros(start_date: date, end_date: date) -> pd.DataFrame:
    """Aggregate area macro metrics over the selected date range."""
    return query(
        """
        WITH aggregated AS (
            SELECT
                area_macro,
                target_scope,
                SUM(active_days) AS active_days,
                SUM(attack_rows) AS attack_rows,
                SUM(launched_total) AS launched_total,
                SUM(destroyed_total) AS destroyed_total
            FROM vw_dashboard_area_macros_daily
            WHERE event_date BETWEEN ? AND ?
            GROUP BY 1, 2
        )
        SELECT
            area_macro,
            target_scope,
            active_days,
            attack_rows,
            launched_total,
            destroyed_total,
            ROUND(100.0 * destroyed_total / NULLIF(launched_total, 0), 2) AS air_defense_success_pct,
            ROUND(100.0 * launched_total / NULLIF(SUM(launched_total) OVER (), 0), 2) AS launched_share_pct
        FROM aggregated
        ORDER BY launched_total DESC, attack_rows DESC, area_macro, target_scope
        """,
        (start_date, end_date),
    )


def get_filtered_directional_macros(start_date: date, end_date: date) -> pd.DataFrame:
    """Aggregate directional macro metrics from the same allocated region data as the specific map."""
    return query(
        f"""
        WITH direction_centroids(area_macro, lat, lon) AS (
            VALUES
                ('north', 51.0, 31.5),
                ('north-east', 50.8, 35.4),
                ('east', 49.0, 36.8),
                ('south-east', 47.7, 35.5),
                ('south', 46.8, 31.5),
                ('center', 49.0, 31.5),
                ('center-east', 48.9, 34.2),
                ('center-west', 49.2, 27.5),
                ('west', 49.5, 24.5)
        ),
        region_daily AS (
            SELECT
                event_date,
                reporting_region,
                SUM(attack_rows) AS attack_rows,
                SUM(launched_total_allocated) AS launched_total,
                SUM(destroyed_total_allocated) AS destroyed_total
            FROM vw_dashboard_region_map_daily
            WHERE event_date BETWEEN ? AND ?
            GROUP BY 1, 2
        ),
        aggregated AS (
            SELECT
                {REGION_MACRO_CASE} AS area_macro,
                COUNT(DISTINCT event_date) AS active_days,
                SUM(attack_rows) AS attack_rows,
                SUM(launched_total) AS launched_total,
                SUM(destroyed_total) AS destroyed_total
            FROM region_daily
            GROUP BY 1
        )
        SELECT
            aggregated.area_macro,
            direction_centroids.lat,
            direction_centroids.lon,
            aggregated.active_days,
            aggregated.attack_rows,
            ROUND(aggregated.launched_total, 2) AS launched_total,
            ROUND(aggregated.destroyed_total, 2) AS destroyed_total,
            ROUND(100.0 * aggregated.destroyed_total / NULLIF(aggregated.launched_total, 0), 2) AS air_defense_success_pct,
            ROUND(100.0 * aggregated.launched_total / NULLIF(SUM(aggregated.launched_total) OVER (), 0), 2) AS launched_share_pct
        FROM aggregated
        JOIN direction_centroids USING (area_macro)
        ORDER BY aggregated.launched_total DESC, aggregated.attack_rows DESC, aggregated.area_macro
        """,
        (start_date, end_date),
    )


def get_filtered_region_map(start_date: date, end_date: date) -> pd.DataFrame:
    """Aggregate specific-region map metrics over the selected date range."""
    return query(
        f"""
        WITH aggregated AS (
            SELECT
                area_region,
                reporting_region,
                MAX(lat) AS lat,
                MAX(lon) AS lon,
                MAX(area_kind) AS area_kind,
                SUM(active_days) AS active_days,
                SUM(attack_rows) AS attack_rows,
                SUM(exploded_region_rows) AS exploded_region_rows,
                SUM(launched_total_exploded) AS launched_total_exploded,
                SUM(destroyed_total_exploded) AS destroyed_total_exploded,
                SUM(launched_total_allocated) AS launched_total_allocated,
                SUM(destroyed_total_allocated) AS destroyed_total_allocated
            FROM vw_dashboard_region_map_daily
            WHERE event_date BETWEEN ? AND ?
            GROUP BY 1, 2
        )
        SELECT
            area_region,
            reporting_region,
            {REGION_MACRO_CASE} AS area_macro,
            lat,
            lon,
            area_kind,
            active_days,
            attack_rows,
            exploded_region_rows,
            launched_total_exploded,
            destroyed_total_exploded,
            ROUND(launched_total_allocated, 2) AS launched_total_allocated,
            ROUND(destroyed_total_allocated, 2) AS destroyed_total_allocated,
            ROUND(100.0 * destroyed_total_allocated / NULLIF(launched_total_allocated, 0), 2) AS air_defense_success_pct,
            ROUND(100.0 * launched_total_allocated / NULLIF(SUM(launched_total_allocated) OVER (), 0), 2) AS launched_share_pct
        FROM aggregated
        ORDER BY attack_rows DESC, launched_total_allocated DESC, area_region
        """,
        (start_date, end_date),
    )
