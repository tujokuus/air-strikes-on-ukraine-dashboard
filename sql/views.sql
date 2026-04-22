CREATE OR REPLACE VIEW vw_dashboard_overview AS
SELECT * FROM mart_overview_summary;


CREATE OR REPLACE VIEW vw_dashboard_daily_activity AS
SELECT * FROM mart_daily_activity
ORDER BY event_date;


CREATE OR REPLACE VIEW vw_dashboard_weapon_models AS
SELECT * FROM mart_weapon_model_summary
ORDER BY launched_total DESC, attack_rows DESC, weapon_model;


CREATE OR REPLACE VIEW vw_dashboard_weapon_types AS
SELECT * FROM mart_weapon_type_summary
ORDER BY launched_total DESC, attack_rows DESC, weapon_category, weapon_type;


CREATE OR REPLACE VIEW vw_dashboard_area_macros AS
SELECT * FROM mart_area_macro_summary
ORDER BY launched_total DESC, attack_rows DESC, area_macro;


CREATE OR REPLACE VIEW vw_dashboard_directional_macros AS
SELECT * FROM mart_directional_macro_summary
ORDER BY launched_total DESC, attack_rows DESC, area_macro;


CREATE OR REPLACE VIEW vw_dashboard_region_map AS
SELECT * FROM mart_region_activity
ORDER BY attack_rows DESC, launched_total_exploded DESC, area_region;
