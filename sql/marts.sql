CREATE OR REPLACE TABLE mart_overview_summary AS
SELECT
    MIN(CAST(NULLIF(event_date, '') AS DATE)) AS first_event_date,
    MAX(CAST(NULLIF(event_date, '') AS DATE)) AS last_event_date,
    COUNT(*) AS total_attack_rows,
    COUNT(DISTINCT NULLIF(event_date, '')) AS distinct_event_dates,
    COUNT(
        DISTINCT CASE
            WHEN COALESCE(NULLIF(TRIM(weapon_model), ''), '') = '' THEN 'Unknown'
            WHEN LOWER(weapon_model) LIKE 'unknown%' THEN 'Unknown'
            ELSE weapon_model
        END
    ) AS distinct_weapon_models,
    COUNT(DISTINCT COALESCE(NULLIF(weapon_category, ''), 'Unknown category')) AS distinct_weapon_categories,
    SUM(COALESCE(launched, 0)) AS total_launched,
    SUM(COALESCE(destroyed, 0)) AS total_destroyed,
    SUM(COALESCE(not_reach_goal, 0)) AS total_not_reach_goal,
    SUM(COALESCE(still_attacking, 0)) AS total_still_attacking,
    SUM(CASE WHEN area_macro = 'nationwide' THEN COALESCE(launched, 0) ELSE 0 END) AS nationwide_launched_total,
    SUM(CASE WHEN area_count > 0 THEN COALESCE(launched, 0) ELSE 0 END) AS specific_area_launched_total,
    SUM(CASE WHEN COALESCE(NULLIF(area_macro, ''), 'unknown') = 'unknown' THEN 1 ELSE 0 END) AS unknown_target_rows,
    SUM(CASE WHEN NOT weapon_reference_match THEN 1 ELSE 0 END) AS unmatched_weapon_reference_rows
FROM silver_attacks;


CREATE OR REPLACE TABLE mart_daily_activity AS
WITH daily AS (
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
    AVG(destroyed_total) OVER (
        ORDER BY event_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS destroyed_7d_avg
FROM daily
ORDER BY event_date;


CREATE OR REPLACE TABLE mart_weapon_model_summary AS
WITH base AS (
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
    ROUND(100.0 * destroyed_total / NULLIF(launched_total, 0), 2) AS destroyed_to_launched_pct,
    first_seen,
    last_seen
FROM grouped
ORDER BY launched_total DESC, attack_rows DESC, weapon_model;


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


CREATE OR REPLACE TABLE mart_area_macro_summary AS
WITH base AS (
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
    ROUND(100.0 * SUM(launched) / NULLIF(SUM(SUM(launched)) OVER (), 0), 2) AS launched_share_pct
FROM base
GROUP BY 1, 2
ORDER BY launched_total DESC, attack_rows DESC, area_macro;


CREATE OR REPLACE TABLE mart_directional_macro_summary AS
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
    ROUND(100.0 * summary.launched_total / NULLIF(SUM(summary.launched_total) OVER (), 0), 2) AS launched_share_pct
FROM summary
LEFT JOIN direction_centroids USING (area_macro)
ORDER BY summary.launched_total DESC, summary.attack_rows DESC, summary.area_macro;


CREATE OR REPLACE TABLE mart_region_activity AS
WITH area_centroids(area_region, lat, lon, area_kind) AS (
    VALUES
        ('Odesa oblast', 46.48, 30.72, 'oblast'),
        ('Mykolaiv oblast', 46.97, 31.99, 'oblast'),
        ('Kyiv oblast', 50.45, 30.52, 'oblast'),
        ('Lviv oblast', 49.84, 24.03, 'oblast'),
        ('Rivne oblast', 50.62, 26.25, 'oblast'),
        ('Volyn oblast', 50.75, 25.33, 'oblast'),
        ('Kherson oblast', 46.64, 32.62, 'oblast'),
        ('Khmelnytskyi oblast', 49.42, 26.99, 'oblast'),
        ('Poltava oblast', 49.59, 34.55, 'oblast'),
        ('Kharkiv oblast', 49.99, 36.23, 'oblast'),
        ('Sumy oblast', 50.91, 34.80, 'oblast'),
        ('Chernihiv oblast', 51.50, 31.29, 'oblast'),
        ('Zaporizhzhia oblast', 47.84, 35.14, 'oblast'),
        ('Dnipropetrovsk oblast', 48.47, 35.04, 'oblast'),
        ('Donetsk oblast', 48.72, 37.55, 'oblast'),
        ('Kirovohrad oblast', 48.51, 32.26, 'oblast'),
        ('Vinnytsia oblast', 49.23, 28.48, 'oblast'),
        ('Cherkasy oblast', 49.44, 32.06, 'oblast'),
        ('Kyiv', 50.45, 30.52, 'city'),
        ('Odesa', 46.48, 30.72, 'city'),
        ('Kharkiv', 49.99, 36.23, 'city'),
        ('Kherson', 46.64, 32.62, 'city'),
        ('Dnipro', 48.47, 35.04, 'city'),
        ('Zaporizhzhia', 47.84, 35.14, 'city'),
        ('Sumy', 50.91, 34.80, 'city'),
        ('Kramatorsk', 48.72, 37.55, 'city'),
        ('Kryvyi Rih', 47.91, 33.39, 'city'),
        ('Starokostiantyniv', 49.76, 27.22, 'city'),
        ('Kolomyia', 48.53, 25.04, 'city'),
        ('Ochakiv', 46.61, 31.54, 'city'),
        ('Snake Island', 45.26, 30.20, 'special')
),
summary AS (
    SELECT
        area_region,
        COUNT(*) AS attack_rows,
        COUNT(DISTINCT CAST(NULLIF(event_date, '') AS DATE)) AS active_days,
        SUM(COALESCE(launched, 0)) AS launched_total_exploded,
        SUM(COALESCE(destroyed, 0)) AS destroyed_total_exploded
    FROM silver_attack_regions
    WHERE has_specific_area_region
      AND area_region <> ''
    GROUP BY 1
)
SELECT
    summary.area_region,
    summary.attack_rows,
    summary.active_days,
    summary.launched_total_exploded,
    summary.destroyed_total_exploded,
    area_centroids.lat,
    area_centroids.lon,
    area_centroids.area_kind,
    ROUND(100.0 * summary.launched_total_exploded / NULLIF(SUM(summary.launched_total_exploded) OVER (), 0), 2) AS launched_share_pct
FROM summary
LEFT JOIN area_centroids USING (area_region)
ORDER BY summary.attack_rows DESC, summary.launched_total_exploded DESC, summary.area_region;
