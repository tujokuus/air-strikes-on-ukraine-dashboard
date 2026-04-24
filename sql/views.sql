-- Dashboard views are the stable read layer for Streamlit.
-- The marts hold the physical aggregated data; these views expose the dashboard-facing names and ordering.

-- Main KPI view for the overview page.
CREATE OR REPLACE VIEW vw_dashboard_overview AS
SELECT * FROM mart_overview_summary;


-- Daily time-series view used by the overview trend chart.
CREATE OR REPLACE VIEW vw_dashboard_daily_activity AS
SELECT * FROM mart_daily_activity
ORDER BY event_date;


-- Daily weapon model view used for future date-range filtering and period rollups.
CREATE OR REPLACE VIEW vw_dashboard_weapon_models_daily AS
SELECT * FROM daily.mart_weapon_model_daily
ORDER BY event_date, launched_total DESC, attack_rows DESC, weapon_model;


-- Daily weapon type view used for future date-range filtering and period rollups.
CREATE OR REPLACE VIEW vw_dashboard_weapon_types_daily AS
SELECT * FROM daily.mart_weapon_type_daily
ORDER BY event_date, launched_total DESC, attack_rows DESC, weapon_category, weapon_type;


-- Daily area macro view used for future date-range filtering and period rollups.
CREATE OR REPLACE VIEW vw_dashboard_area_macros_daily AS
SELECT * FROM daily.mart_area_macro_daily
ORDER BY event_date, launched_total DESC, attack_rows DESC, area_macro, target_scope;


-- Daily directional macro view used for future date-range filtering and map rollups.
CREATE OR REPLACE VIEW vw_dashboard_directional_macros_daily AS
SELECT * FROM daily.mart_directional_macro_daily
ORDER BY event_date, launched_total DESC, attack_rows DESC, area_macro;


-- Daily region map view used for future date-range filtering and map rollups.
CREATE OR REPLACE VIEW vw_dashboard_region_map_daily AS
SELECT * FROM daily.mart_region_daily
ORDER BY event_date, attack_rows DESC, launched_total_allocated DESC, area_region;


-- Weapon model view used by top weapon model charts and coverage tables.
CREATE OR REPLACE VIEW vw_dashboard_weapon_models AS
SELECT * FROM mart_weapon_model_summary
ORDER BY launched_total DESC, attack_rows DESC, weapon_model;


-- Weapon type view used when the dashboard groups models into broader types.
CREATE OR REPLACE VIEW vw_dashboard_weapon_types AS
SELECT * FROM mart_weapon_type_summary
ORDER BY launched_total DESC, attack_rows DESC, weapon_category, weapon_type;


-- Target scope view for nationwide, regional, directional, and unknown target summaries.
CREATE OR REPLACE VIEW vw_dashboard_area_macros AS
SELECT * FROM mart_area_macro_summary
ORDER BY launched_total DESC, attack_rows DESC, area_macro;


-- Coarse map view for directional macro areas.
CREATE OR REPLACE VIEW vw_dashboard_directional_macros AS
SELECT * FROM mart_directional_macro_summary
ORDER BY launched_total DESC, attack_rows DESC, area_macro;


-- Specific region map view based on the exploded region mart.
CREATE OR REPLACE VIEW vw_dashboard_region_map AS
SELECT * FROM mart_region_activity
ORDER BY attack_rows DESC, launched_total_exploded DESC, area_region;
