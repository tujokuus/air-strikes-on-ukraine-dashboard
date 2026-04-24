-- Daily marts keep one row per date plus the relevant analysis grain.
-- These tables support date-range filtering without recomputing everything from raw bronze data.

CREATE SCHEMA IF NOT EXISTS daily;

-- Remove legacy daily tables from the default schema after moving them into `daily`.
DROP TABLE IF EXISTS mart_weapon_model_daily;
DROP TABLE IF EXISTS mart_weapon_type_daily;
DROP TABLE IF EXISTS mart_area_macro_daily;
DROP TABLE IF EXISTS mart_directional_macro_daily;
DROP TABLE IF EXISTS mart_region_daily;

-- Weapon model daily summary.
CREATE OR REPLACE TABLE daily.mart_weapon_model_daily AS
WITH base AS (
    SELECT
        CAST(NULLIF(event_date, '') AS DATE) AS event_date,
        CASE
            WHEN COALESCE(NULLIF(TRIM(weapon_model), ''), '') = '' THEN 'Unknown'
            WHEN LOWER(weapon_model) LIKE 'unknown%' THEN 'Unknown'
            ELSE weapon_model
        END AS weapon_model,
        CASE
            WHEN COALESCE(NULLIF(TRIM(weapon_model_key), ''), '') = '' THEN 'unknown'
            ELSE weapon_model_key
        END AS weapon_model_key,
        COALESCE(NULLIF(weapon_category, ''), 'Unknown category') AS weapon_category,
        COALESCE(NULLIF(weapon_type, ''), 'Unknown type') AS weapon_type,
        weapon_reference_match,
        COALESCE(launched, 0) AS launched,
        COALESCE(destroyed, 0) AS destroyed
    FROM silver_attacks
    WHERE event_date <> ''
),
grouped AS (
    SELECT
        event_date,
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
        1 AS active_days,
        COUNT(*) AS attack_rows,
        SUM(launched) AS launched_total,
        SUM(destroyed) AS destroyed_total,
        SUM(CASE WHEN weapon_reference_match THEN 1 ELSE 0 END) AS matched_rows,
        SUM(CASE WHEN NOT weapon_reference_match THEN 1 ELSE 0 END) AS unmatched_rows
    FROM base
    GROUP BY 1, 2, 3
)
SELECT
    event_date,
    weapon_model_key,
    weapon_model,
    weapon_category,
    weapon_type,
    active_days,
    attack_rows,
    launched_total,
    destroyed_total,
    matched_rows,
    unmatched_rows
FROM grouped
ORDER BY event_date, launched_total DESC, attack_rows DESC, weapon_model;


-- Weapon type daily summary.
CREATE OR REPLACE TABLE daily.mart_weapon_type_daily AS
SELECT
    CAST(NULLIF(event_date, '') AS DATE) AS event_date,
    COALESCE(NULLIF(weapon_category, ''), 'Unknown category') AS weapon_category,
    COALESCE(NULLIF(weapon_type, ''), 'Unknown type') AS weapon_type,
    1 AS active_days,
    COUNT(*) AS attack_rows,
    SUM(COALESCE(launched, 0)) AS launched_total,
    SUM(COALESCE(destroyed, 0)) AS destroyed_total,
    SUM(CASE WHEN weapon_reference_match THEN 1 ELSE 0 END) AS matched_rows,
    SUM(CASE WHEN NOT weapon_reference_match THEN 1 ELSE 0 END) AS unmatched_rows
FROM silver_attacks
WHERE event_date <> ''
GROUP BY 1, 2, 3
ORDER BY event_date, launched_total DESC, attack_rows DESC, weapon_category, weapon_type;


-- Area macro daily summary.
CREATE OR REPLACE TABLE daily.mart_area_macro_daily AS
WITH base AS (
    SELECT
        CAST(NULLIF(event_date, '') AS DATE) AS event_date,
        COALESCE(NULLIF(area_macro, ''), 'unknown') AS area_macro,
        CASE
            WHEN area_macro = 'nationwide' THEN 'nationwide'
            WHEN area_count > 0 THEN 'specific_area_rows'
            WHEN COALESCE(NULLIF(area_macro, ''), 'unknown') = 'unknown' THEN 'unknown'
            ELSE 'directional_or_other_macro'
        END AS target_scope,
        COALESCE(launched, 0) AS launched,
        COALESCE(destroyed, 0) AS destroyed
    FROM silver_attacks
    WHERE event_date <> ''
)
SELECT
    event_date,
    area_macro,
    target_scope,
    1 AS active_days,
    COUNT(*) AS attack_rows,
    SUM(launched) AS launched_total,
    SUM(destroyed) AS destroyed_total
FROM base
GROUP BY 1, 2, 3
ORDER BY event_date, launched_total DESC, attack_rows DESC, area_macro, target_scope;


-- Directional macro daily summary for the coarse map.
CREATE OR REPLACE TABLE daily.mart_directional_macro_daily AS
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
summary AS (
    SELECT
        CAST(NULLIF(event_date, '') AS DATE) AS event_date,
        area_macro,
        COUNT(*) AS attack_rows,
        SUM(COALESCE(launched, 0)) AS launched_total,
        SUM(COALESCE(destroyed, 0)) AS destroyed_total
    FROM silver_attacks
    WHERE event_date <> ''
      AND area_macro IN (
        'north', 'south', 'east', 'west', 'center',
        'north-east', 'south-east', 'center-east', 'center-west'
      )
    GROUP BY 1, 2
)
SELECT
    summary.event_date,
    summary.area_macro,
    direction_centroids.lat,
    direction_centroids.lon,
    1 AS active_days,
    summary.attack_rows,
    summary.launched_total,
    summary.destroyed_total
FROM summary
LEFT JOIN direction_centroids USING (area_macro)
ORDER BY summary.event_date, summary.launched_total DESC, summary.attack_rows DESC, summary.area_macro;


-- Specific region daily summary.
CREATE OR REPLACE TABLE daily.mart_region_daily AS
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
    SELECT
        CAST(NULLIF(silver_attack_regions.event_date, '') AS DATE) AS event_date,
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
    WHERE silver_attack_regions.event_date <> ''
      AND has_specific_area_region
      AND silver_attack_regions.area_region <> ''
),
summary AS (
    SELECT
        event_date,
        reporting_region,
        COUNT(DISTINCT source_record_key) AS attack_rows,
        COUNT(*) AS exploded_region_rows,
        SUM(launched) AS launched_total_exploded,
        SUM(destroyed) AS destroyed_total_exploded,
        SUM(launched_allocated) AS launched_total_allocated,
        SUM(destroyed_allocated) AS destroyed_total_allocated,
        MAX(lat) AS lat,
        MAX(lon) AS lon,
        MAX(area_kind) AS area_kind
    FROM mapped
    GROUP BY 1, 2
)
SELECT
    event_date,
    summary.reporting_region AS area_region,
    summary.reporting_region,
    summary.lat,
    summary.lon,
    summary.area_kind,
    1 AS active_days,
    summary.attack_rows,
    summary.exploded_region_rows,
    summary.launched_total_exploded,
    summary.destroyed_total_exploded,
    ROUND(summary.launched_total_allocated, 2) AS launched_total_allocated,
    ROUND(summary.destroyed_total_allocated, 2) AS destroyed_total_allocated
FROM summary
ORDER BY summary.event_date, summary.attack_rows DESC, summary.launched_total_allocated DESC, summary.reporting_region;
