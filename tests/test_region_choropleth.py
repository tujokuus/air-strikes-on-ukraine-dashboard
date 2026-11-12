import pandas as pd

from dashboard.maps import load_region_boundaries, make_region_features, prepare_direction_markers


def test_oblasts_use_selected_metric_and_missing_regions_stay_neutral():
    data = pd.DataFrame([
        {'reporting_region': 'Kyiv oblast', 'attack_rows': 10, 'launched_total_allocated': 2.5},
        {'reporting_region': 'Odesa oblast', 'attack_rows': 5, 'launched_total_allocated': 10},
        {'reporting_region': 'Kursk oblast', 'attack_rows': 9999, 'launched_total_allocated': 9999},
    ])
    collection, maximum = make_region_features(load_region_boundaries(), data, 'launched_total_allocated')
    features = {f['properties']['name']: f['properties'] for f in collection['features']}
    assert maximum == 10
    assert features['Kyiv oblast']['value_label'] == '2.5'
    assert features['Odesa oblast']['value_label'] == '10'
    assert features['Lviv oblast']['value_label'] == 'Not available'
    assert features['Odesa oblast']['fill_color'] != features['Kyiv oblast']['fill_color']
    assert features['Lviv oblast']['fill_color'] != features['Kyiv oblast']['fill_color']


def test_region_metric_can_be_switched():
    data = pd.DataFrame([{'reporting_region': 'Kyiv oblast', 'attack_rows': 7, 'launched_total_allocated': 2}])
    collection, maximum = make_region_features(load_region_boundaries(), data, 'attack_rows')
    kyiv = next(f for f in collection['features'] if f['properties']['name'] == 'Kyiv oblast')
    assert maximum == 7
    assert kyiv['properties']['value_label'] == '7'


def test_percentage_scale_is_fixed_at_100():
    data = pd.DataFrame([{'reporting_region': 'Kyiv oblast', 'attack_rows': 7, 'air_defense_success_pct': 25}])
    _, maximum = make_region_features(load_region_boundaries(), data, 'air_defense_success_pct')
    assert maximum == 100


def test_direction_map_includes_only_broad_directional_reports():
    data = pd.DataFrame([
        {'area_macro': 'south', 'target_scope': 'directional_or_other_macro', 'attack_rows': 12, 'launched_total': 100},
        {'area_macro': 'south', 'target_scope': 'specific_area_rows', 'attack_rows': 30, 'launched_total': 10000},
        {'area_macro': 'multi', 'target_scope': 'directional_or_other_macro', 'attack_rows': 5, 'launched_total': 5000},
        {'area_macro': 'nationwide', 'target_scope': 'nationwide', 'attack_rows': 7, 'launched_total': 10000},
    ])
    markers, maximum = prepare_direction_markers(data, 'launched_total')
    assert len(markers) == 1
    assert markers[0]['direction'] == 'South'
    assert markers[0]['value_label'] == '100'
    assert maximum == 100


def test_direction_map_omits_unavailable_metric():
    data = pd.DataFrame([{'area_macro': 'north', 'target_scope': 'directional_or_other_macro',
                          'attack_rows': 1, 'air_defense_success_pct': None}])
    markers, maximum = prepare_direction_markers(data, 'air_defense_success_pct')
    assert not markers
    assert maximum == 100
