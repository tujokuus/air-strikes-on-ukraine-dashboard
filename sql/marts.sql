-- Gold marts are physical analytics tables built from the silver layer.
-- They contain pre-aggregated data so the dashboard can load quickly and stay simple.

-- One-row dashboard summary for the main KPI cards.
CREATE OR REPLACE TABLE mart_overview_summary AS
WITH normalized AS (
    -- Normalize fields once so the summary totals and top-model metrics use the same labels.
    SELECT
        *,
        CASE
            WHEN COALESCE(NULLIF(TRIM(weapon_model), ''), '') = '' THEN 'Unknown'
            WHEN LOWER(weapon_model) LIKE 'unknown%' THEN 'Unknown'
            ELSE weapon_model
        END AS normalized_weapon_model,
        CASE
            WHEN COALESCE(NULLIF(TRIM(weapon_model_key), ''), '') = '' THEN 'unknown'
            ELSE weapon_model_key
        END AS normalized_weapon_model_key,
        COALESCE(NULLIF(weapon_category, ''), 'Unknown category') AS normalized_weapon_category,
        COALESCE(launched, 0) AS launched_value,
        COALESCE(destroyed, 0) AS destroyed_value,
        COALESCE(not_reach_goal, 0) AS not_reach_goal_value,
        COALESCE(still_attacking, 0) AS still_attacking_value
    FROM silver_attacks
),
overview AS (
SELECT
    MIN(CAST(NULLIF(event_date, '') AS DATE)) AS first_event_date,
    MAX(CAST(NULLIF(event_date, '') AS DATE)) AS last_event_date,
    COUNT(*) AS total_attack_rows,
    COUNT(DISTINCT NULLIF(event_date, '')) AS distinct_event_dates,
    COUNT(DISTINCT normalized_weapon_model_key) AS distinct_weapon_models,
    COUNT(DISTINCT normalized_weapon_category) AS distinct_weapon_categories,
    SUM(launched_value) AS total_launched,
    SUM(destroyed_value) AS total_destroyed,
    SUM(not_reach_goal_value) AS total_not_reach_goal,
    SUM(still_attacking_value) AS total_still_attacking,
    SUM(CASE WHEN area_macro = 'nationwide' THEN launched_value ELSE 0 END) AS nationwide_launched_total,
    SUM(CASE WHEN area_count > 0 THEN launched_value ELSE 0 END) AS specific_area_launched_total,
    SUM(CASE WHEN COALESCE(NULLIF(area_macro, ''), 'unknown') = 'unknown' THEN 1 ELSE 0 END) AS unknown_target_rows,
    SUM(CASE WHEN NOT weapon_reference_match THEN 1 ELSE 0 END) AS unmatched_weapon_reference_rows
FROM normalized
),
top_uav AS (
    -- Top UAV is selected by launched total across all rows for each cleaned weapon model key.
    SELECT
        normalized_weapon_model_key AS top_uav_weapon_model_key,
        SUM(launched_value) AS top_uav_launched
    FROM normalized
    WHERE LOWER(normalized_weapon_category) = 'uav'
    GROUP BY 1
    ORDER BY top_uav_launched DESC, top_uav_weapon_model_key
    LIMIT 1
),
top_cruise_missile AS (
    -- Cruise missiles are calculated separately from ballistic missiles.
    SELECT
        normalized_weapon_model_key AS top_cruise_missile_weapon_model_key,
        SUM(launched_value) AS top_cruise_missile_launched
    FROM normalized
    WHERE LOWER(normalized_weapon_category) = 'cruise missile'
    GROUP BY 1
    ORDER BY top_cruise_missile_launched DESC, top_cruise_missile_weapon_model_key
    LIMIT 1
),
top_ballistic_missile AS (
    -- Ballistic calculation includes categories that explicitly contain ballistic.
    SELECT
        normalized_weapon_model_key AS top_ballistic_missile_weapon_model_key,
        SUM(launched_value) AS top_ballistic_missile_launched
    FROM normalized
    WHERE LOWER(normalized_weapon_category) LIKE '%ballistic%'
    GROUP BY 1
    ORDER BY top_ballistic_missile_launched DESC, top_ballistic_missile_weapon_model_key
    LIMIT 1
)
SELECT
    overview.*,
    top_uav.top_uav_weapon_model_key,
    top_uav.top_uav_launched,
    top_cruise_missile.top_cruise_missile_weapon_model_key,
    top_cruise_missile.top_cruise_missile_launched,
    top_ballistic_missile.top_ballistic_missile_weapon_model_key,
    top_ballistic_missile.top_ballistic_missile_launched
FROM overview
LEFT JOIN top_uav ON TRUE
LEFT JOIN top_cruise_missile ON TRUE
LEFT JOIN top_ballistic_missile ON TRUE;


-- Daily trend table for time-series charts.
CREATE OR REPLACE TABLE mart_daily_activity AS
WITH daily AS (
    -- First aggregate raw strike rows to one row per event date.
    SELECT
        CAST(event_date AS DATE) AS event_date,
        COUNT(*) AS attack_rows,
        COUNT(
            DISTINCT CASE
                WHEN COALESCE(NULLIF(TRIM(weapon_model), ''), '') = '' THEN 'Unknown'
                WHEN LOWER(weapon_model) LIKE 'unknown%' THEN 'Unknown'
                ELSE weapon_model
            END
        ) AS distinct_weapon_models,
        SUM(COALESCE(launched, 0)) AS launched_total,
        SUM(COALESCE(destroyed, 0)) AS destroyed_total,
        SUM(COALESCE(not_reach_goal, 0)) AS not_reach_goal_total,
        SUM(COALESCE(still_attacking, 0)) AS still_attacking_total
    FROM silver_attacks
    WHERE event_date <> ''
    GROUP BY 1
)
SELECT
    event_date,
    attack_rows,
    distinct_weapon_models,
    launched_total,
    destroyed_total,
    not_reach_goal_total,
    still_attacking_total,
    AVG(launched_total) OVER (
        ORDER BY event_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS launched_7d_avg,
    -- Seven-day rolling averages smooth noisy daily changes in the dashboard line chart.
    AVG(destroyed_total) OVER (
        ORDER BY event_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS destroyed_7d_avg
FROM daily
ORDER BY event_date;


-- Weapon model level summary for top-model charts and reference coverage checks.
CREATE OR REPLACE TABLE mart_weapon_model_summary AS
WITH base AS (
    -- Normalize empty or unknown model names before grouping.
    SELECT
        CASE
            WHEN COALESCE(NULLIF(TRIM(weapon_model), ''), '') = '' THEN 'Unknown'
            WHEN LOWER(weapon_model) LIKE 'unknown%' THEN 'Unknown'
            ELSE weapon_model
        END AS weapon_model,
        COALESCE(NULLIF(weapon_category, ''), 'Unknown category') AS weapon_category,
        COALESCE(NULLIF(weapon_type, ''), 'Unknown type') AS weapon_type,
        weapon_reference_match,
        CAST(NULLIF(event_date, '') AS DATE) AS event_date,
        COALESCE(launched, 0) AS launched,
        COALESCE(destroyed, 0) AS destroyed
    FROM silver_attacks
),
grouped AS (
    -- Group by normalized weapon model and keep useful first/last activity dates.
    SELECT
        weapon_model,
        CASE
            WHEN COUNT(DISTINCT weapon_category) = 1 THEN MIN(weapon_category)
            ELSE 'Mixed'
        END AS weapon_category,
        CASE
            WHEN COUNT(DISTINCT weapon_type) = 1 THEN MIN(weapon_type)
            ELSE 'Mixed/Various'
        END AS weapon_type,
        COUNT(*) AS attack_rows,
        COUNT(DISTINCT event_date) AS active_days,
        SUM(launched) AS launched_total,
        SUM(destroyed) AS destroyed_total,
        SUM(CASE WHEN weapon_reference_match THEN 1 ELSE 0 END) AS matched_rows,
        SUM(CASE WHEN NOT weapon_reference_match THEN 1 ELSE 0 END) AS unmatched_rows,
        MIN(event_date) AS first_seen,
        MAX(event_date) AS last_seen
    FROM base
    GROUP BY 1
)
SELECT
    weapon_model,
    weapon_category,
    weapon_type,
    attack_rows,
    active_days,
    launched_total,
    destroyed_total,
    matched_rows,
    unmatched_rows,
    ROUND(100.0 * matched_rows / NULLIF(attack_rows, 0), 2) AS reference_coverage_pct,
    ROUND(100.0 * launched_total / NULLIF(SUM(launched_total) OVER (), 0), 2) AS launched_share_pct,
    -- Destruction percentage is calculated against launched count for the same model.
    ROUND(100.0 * destroyed_total / NULLIF(launched_total, 0), 2) AS destroyed_to_launched_pct,
    first_seen,
    last_seen
FROM grouped
ORDER BY launched_total DESC, attack_rows DESC, weapon_model;


-- Broader weapon type summary, useful when model names are too detailed for a chart.
CREATE OR REPLACE TABLE mart_weapon_type_summary AS
SELECT
    COALESCE(NULLIF(weapon_category, ''), 'Unknown category') AS weapon_category,
    COALESCE(NULLIF(weapon_type, ''), 'Unknown type') AS weapon_type,
    COUNT(*) AS attack_rows,
    COUNT(DISTINCT CAST(NULLIF(event_date, '') AS DATE)) AS active_days,
    SUM(COALESCE(launched, 0)) AS launched_total,
    SUM(COALESCE(destroyed, 0)) AS destroyed_total,
    SUM(CASE WHEN weapon_reference_match THEN 1 ELSE 0 END) AS matched_rows,
    SUM(CASE WHEN NOT weapon_reference_match THEN 1 ELSE 0 END) AS unmatched_rows,
    ROUND(100.0 * SUM(COALESCE(launched, 0)) / NULLIF(SUM(SUM(COALESCE(launched, 0))) OVER (), 0), 2) AS launched_share_pct
FROM silver_attacks
GROUP BY 1, 2
ORDER BY launched_total DESC, attack_rows DESC, weapon_category, weapon_type;


-- Target scope summary: nationwide rows, specific area rows, unknowns, and directional macros.
CREATE OR REPLACE TABLE mart_area_macro_summary AS
WITH base AS (
    -- target_scope makes the dashboard labels easier to interpret than raw area_macro alone.
    SELECT
        COALESCE(NULLIF(area_macro, ''), 'unknown') AS area_macro,
        CASE
            WHEN area_macro = 'nationwide' THEN 'nationwide'
            WHEN area_count > 0 THEN 'specific_area_rows'
            WHEN COALESCE(NULLIF(area_macro, ''), 'unknown') = 'unknown' THEN 'unknown'
            ELSE 'directional_or_other_macro'
        END AS target_scope,
        CAST(NULLIF(event_date, '') AS DATE) AS event_date,
        COALESCE(launched, 0) AS launched,
        COALESCE(destroyed, 0) AS destroyed
    FROM silver_attacks
)
SELECT
    area_macro,
    target_scope,
    COUNT(*) AS attack_rows,
    COUNT(DISTINCT event_date) AS active_days,
    SUM(launched) AS launched_total,
    SUM(destroyed) AS destroyed_total,
    ROUND(100.0 * SUM(destroyed) / NULLIF(SUM(launched), 0), 2) AS air_defense_success_pct,
    ROUND(100.0 * SUM(launched) / NULLIF(SUM(SUM(launched)) OVER (), 0), 2) AS launched_share_pct
FROM base
GROUP BY 1, 2
ORDER BY launched_total DESC, attack_rows DESC, area_macro;


-- Directional macro summary for the coarse map: north, east, south, center, west, etc.
CREATE OR REPLACE TABLE mart_directional_macro_summary AS
WITH direction_centroids(area_macro, lat, lon) AS (
    -- These are approximate centroid points for dashboard visualization, not exact boundaries.
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
summary AS (
    -- Keep only directional macro values that have matching centroid coordinates.
    SELECT
        area_macro,
        COUNT(*) AS attack_rows,
        COUNT(DISTINCT CAST(NULLIF(event_date, '') AS DATE)) AS active_days,
        SUM(COALESCE(launched, 0)) AS launched_total,
        SUM(COALESCE(destroyed, 0)) AS destroyed_total
    FROM silver_attacks
    WHERE area_macro IN (
        'north', 'south', 'east', 'west', 'center',
        'north-east', 'south-east', 'center-east', 'center-west'
    )
    GROUP BY 1
)
SELECT
    summary.area_macro,
    summary.attack_rows,
    summary.active_days,
    summary.launched_total,
    summary.destroyed_total,
    direction_centroids.lat,
    direction_centroids.lon,
    ROUND(100.0 * summary.destroyed_total / NULLIF(summary.launched_total, 0), 2) AS air_defense_success_pct,
    ROUND(100.0 * summary.launched_total / NULLIF(SUM(summary.launched_total) OVER (), 0), 2) AS launched_share_pct
FROM summary
-- LEFT JOIN keeps the summary row even if a centroid is missing, which helps reveal mapping gaps.
LEFT JOIN direction_centroids USING (area_macro)
ORDER BY summary.launched_total DESC, summary.attack_rows DESC, summary.area_macro;


-- Specific region summary for the region map.
CREATE OR REPLACE TABLE mart_region_activity AS
WITH area_lookup(
    area_region,
    reporting_region,
    lat,
    lon,
    area_kind,
    reporting_lat,
    reporting_lon,
    reporting_area_kind
) AS (
    -- Approximate point coordinates for source regions plus an oblast-level reporting region.
    VALUES
        ('Odesa oblast', 'Odesa oblast', 46.48, 30.72, 'oblast', 46.48, 30.72, 'oblast'),
        ('Mykolaiv oblast', 'Mykolaiv oblast', 46.97, 31.99, 'oblast', 46.97, 31.99, 'oblast'),
        ('Kyiv oblast', 'Kyiv oblast', 50.45, 30.52, 'oblast', 50.45, 30.52, 'oblast'),
        ('Lviv oblast', 'Lviv oblast', 49.84, 24.03, 'oblast', 49.84, 24.03, 'oblast'),
        ('Rivne oblast', 'Rivne oblast', 50.62, 26.25, 'oblast', 50.62, 26.25, 'oblast'),
        ('Volyn oblast', 'Volyn oblast', 50.75, 25.33, 'oblast', 50.75, 25.33, 'oblast'),
        ('Kherson oblast', 'Kherson oblast', 46.64, 32.62, 'oblast', 46.64, 32.62, 'oblast'),
        ('Khmelnytskyi oblast', 'Khmelnytskyi oblast', 49.42, 26.99, 'oblast', 49.42, 26.99, 'oblast'),
        ('Poltava oblast', 'Poltava oblast', 49.59, 34.55, 'oblast', 49.59, 34.55, 'oblast'),
        ('Kharkiv oblast', 'Kharkiv oblast', 49.99, 36.23, 'oblast', 49.99, 36.23, 'oblast'),
        ('Sumy oblast', 'Sumy oblast', 50.91, 34.80, 'oblast', 50.91, 34.80, 'oblast'),
        ('Chernihiv oblast', 'Chernihiv oblast', 51.50, 31.29, 'oblast', 51.50, 31.29, 'oblast'),
        ('Zaporizhzhia oblast', 'Zaporizhzhia oblast', 47.84, 35.14, 'oblast', 47.84, 35.14, 'oblast'),
        ('Dnipropetrovsk oblast', 'Dnipropetrovsk oblast', 48.47, 35.04, 'oblast', 48.47, 35.04, 'oblast'),
        ('Donetsk oblast', 'Donetsk oblast', 48.72, 37.55, 'oblast', 48.72, 37.55, 'oblast'),
        ('Kirovohrad oblast', 'Kirovohrad oblast', 48.51, 32.26, 'oblast', 48.51, 32.26, 'oblast'),
        ('Vinnytsia oblast', 'Vinnytsia oblast', 49.23, 28.48, 'oblast', 49.23, 28.48, 'oblast'),
        ('Cherkasy oblast', 'Cherkasy oblast', 49.44, 32.06, 'oblast', 49.44, 32.06, 'oblast'),
        ('Ivano-Frankivsk oblast', 'Ivano-Frankivsk oblast', 48.92, 24.71, 'oblast', 48.92, 24.71, 'oblast'),
        ('Kursk oblast', 'Kursk oblast', 51.73, 36.19, 'foreign_oblast', 51.73, 36.19, 'foreign_oblast'),
        ('Kyiv', 'Kyiv oblast', 50.45, 30.52, 'city', 50.45, 30.52, 'oblast'),
        ('Odesa', 'Odesa oblast', 46.48, 30.72, 'city', 46.48, 30.72, 'oblast'),
        ('Kharkiv', 'Kharkiv oblast', 49.99, 36.23, 'city', 49.99, 36.23, 'oblast'),
        ('Kherson', 'Kherson oblast', 46.64, 32.62, 'city', 46.64, 32.62, 'oblast'),
        ('Dnipro', 'Dnipropetrovsk oblast', 48.47, 35.04, 'city', 48.47, 35.04, 'oblast'),
        ('Zaporizhzhia', 'Zaporizhzhia oblast', 47.84, 35.14, 'city', 47.84, 35.14, 'oblast'),
        ('Sumy', 'Sumy oblast', 50.91, 34.80, 'city', 50.91, 34.80, 'oblast'),
        ('Kramatorsk', 'Donetsk oblast', 48.72, 37.55, 'city', 48.72, 37.55, 'oblast'),
        ('Kryvyi Rih', 'Dnipropetrovsk oblast', 47.91, 33.39, 'city', 48.47, 35.04, 'oblast'),
        ('Starokostiantyniv', 'Khmelnytskyi oblast', 49.76, 27.22, 'city', 49.42, 26.99, 'oblast'),
        ('Kolomyia', 'Ivano-Frankivsk oblast', 48.53, 25.04, 'city', 48.92, 24.71, 'oblast'),
        ('Ochakiv', 'Mykolaiv oblast', 46.61, 31.54, 'city', 46.97, 31.99, 'oblast'),
        ('Snake Island', 'Odesa oblast', 45.26, 30.20, 'special', 46.48, 30.72, 'oblast')
),
mapped AS (
    -- Keep full exploded totals, but also allocate each row across its listed area_count.
    SELECT
        COALESCE(area_lookup.reporting_region, silver_attack_regions.area_region) AS reporting_region,
        silver_attack_regions.area_region AS source_area_region,
        COALESCE(area_lookup.reporting_lat, area_lookup.lat) AS lat,
        COALESCE(area_lookup.reporting_lon, area_lookup.lon) AS lon,
        COALESCE(area_lookup.reporting_area_kind, area_lookup.area_kind, 'unmapped') AS area_kind,
        CONCAT(
            COALESCE(silver_attack_regions.source_file, ''),
            ':',
            CAST(silver_attack_regions.source_row_number AS VARCHAR)
        ) AS source_record_key,
        CAST(NULLIF(silver_attack_regions.event_date, '') AS DATE) AS event_date,
        COALESCE(silver_attack_regions.launched, 0) AS launched,
        COALESCE(silver_attack_regions.destroyed, 0) AS destroyed,
        CASE
            WHEN COALESCE(silver_attack_regions.area_count, 0) > 0
                THEN CAST(COALESCE(silver_attack_regions.launched, 0) AS DOUBLE) / silver_attack_regions.area_count
            ELSE CAST(COALESCE(silver_attack_regions.launched, 0) AS DOUBLE)
        END AS launched_allocated,
        CASE
            WHEN COALESCE(silver_attack_regions.area_count, 0) > 0
                THEN CAST(COALESCE(silver_attack_regions.destroyed, 0) AS DOUBLE) / silver_attack_regions.area_count
            ELSE CAST(COALESCE(silver_attack_regions.destroyed, 0) AS DOUBLE)
        END AS destroyed_allocated
    FROM silver_attack_regions
    LEFT JOIN area_lookup USING (area_region)
    WHERE has_specific_area_region
      AND silver_attack_regions.area_region <> ''
),
summary AS (
    SELECT
        reporting_region,
        COUNT(DISTINCT source_record_key) AS attack_rows,
        COUNT(*) AS exploded_region_rows,
        COUNT(DISTINCT source_area_region) AS source_region_count,
        COUNT(DISTINCT event_date) AS active_days,
        SUM(launched) AS launched_total_exploded,
        SUM(destroyed) AS destroyed_total_exploded,
        SUM(launched_allocated) AS launched_total_allocated,
        SUM(destroyed_allocated) AS destroyed_total_allocated,
        MAX(lat) AS lat,
        MAX(lon) AS lon,
        MAX(area_kind) AS area_kind
    FROM mapped
    GROUP BY 1
)
SELECT
    summary.reporting_region AS area_region,
    summary.reporting_region,
    summary.attack_rows,
    summary.exploded_region_rows,
    summary.source_region_count,
    summary.active_days,
    summary.launched_total_exploded,
    summary.destroyed_total_exploded,
    ROUND(summary.launched_total_allocated, 2) AS launched_total_allocated,
    ROUND(summary.destroyed_total_allocated, 2) AS destroyed_total_allocated,
    summary.lat,
    summary.lon,
    summary.area_kind,
    ROUND(100.0 * summary.destroyed_total_allocated / NULLIF(summary.launched_total_allocated, 0), 2) AS air_defense_success_pct,
    ROUND(100.0 * summary.launched_total_allocated / NULLIF(SUM(summary.launched_total_allocated) OVER (), 0), 2) AS launched_share_pct
FROM summary
-- Missing coordinates stay visible as NULLs so unmapped regions can be detected later.
ORDER BY summary.attack_rows DESC, summary.launched_total_allocated DESC, summary.reporting_region;
