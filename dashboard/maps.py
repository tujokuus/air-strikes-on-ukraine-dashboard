from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st


REGION_NAMES = {
    'Автономна Республіка Крим': 'Crimea', 'Вінницька область': 'Vinnytsia oblast',
    'Волинська область': 'Volyn oblast', 'Дніпропетровська область': 'Dnipropetrovsk oblast',
    'Донецька область': 'Donetsk oblast', 'Житомирська область': 'Zhytomyr oblast',
    'Закарпатська область': 'Zakarpattia oblast', 'Запорізька область': 'Zaporizhzhia oblast',
    'Івано-Франківська область': 'Ivano-Frankivsk oblast', 'Кіровоградська область': 'Kirovohrad oblast',
    'Луганська область': 'Luhansk oblast', 'Львівська область': 'Lviv oblast',
    'Миколаївська область': 'Mykolaiv oblast', 'Одеська область': 'Odesa oblast',
    'Полтавська область': 'Poltava oblast', 'Рівненська область': 'Rivne oblast',
    'Сумська область': 'Sumy oblast', 'Тернопільська область': 'Ternopil oblast',
    'Харківська область': 'Kharkiv oblast', 'Хмельницька область': 'Khmelnytskyi oblast',
    'Черкаська область': 'Cherkasy oblast', 'Чернівецька область': 'Chernivtsi oblast',
    'Чернігівська область': 'Chernihiv oblast', 'Херсонська область': 'Kherson oblast',
    'Київська область': 'Kyiv oblast', 'Севастополь': 'Sevastopol',
}
REGION_BOUNDARIES = Path(__file__).parent / 'assets' / 'ukraine_regions.geojson'
DIRECTION_CENTERS = {
    'north': (31.5, 51.0), 'north-east': (35.4, 50.8), 'east': (36.8, 49.0),
    'south-east': (35.5, 47.7), 'south': (31.5, 46.8), 'center': (31.5, 49.0),
    'center-east': (34.2, 48.9), 'center-west': (27.5, 49.2), 'west': (24.5, 49.5),
}


@st.cache_data(show_spinner=False)
def load_region_boundaries() -> dict:
    return json.loads(REGION_BOUNDARIES.read_text(encoding='utf-8'))


def make_region_features(boundaries: dict, frame: pd.DataFrame, metric: str) -> tuple[dict, float]:
    """Join reporting oblasts to polygons, leaving unmapped regions neutral."""
    if frame['reporting_region'].duplicated().any():
        raise ValueError('Expected one row per reporting region')
    rows = frame.set_index('reporting_region').to_dict('index')
    boundary_names = {REGION_NAMES.get(f['properties']['region'], f['properties']['region']) for f in boundaries['features']}
    known = pd.to_numeric(frame.loc[frame['reporting_region'].isin(boundary_names), metric], errors='coerce').dropna()
    maximum = 100.0 if metric == 'air_defense_success_pct' else (max(float(known.max()), 0.0) if not known.empty else 0.0)
    features = []
    for feature in boundaries['features']:
        name = REGION_NAMES.get(feature['properties']['region'], feature['properties']['region'])
        row = rows.get(name)
        value = row.get(metric) if row is not None else None
        valid = value is not None and pd.notna(value)
        ratio = max(0.0, float(value)) / maximum if valid and maximum > 0 else 0.0
        if metric != 'air_defense_success_pct':
            ratio = ratio ** 0.5
        high = [83, 173, 134, 240] if metric == 'air_defense_success_pct' else [224, 131, 62, 240]
        color = interpolate_rgba([43, 67, 92, 230], high, ratio) if valid else [29, 42, 59, 220]
        props = {
            'name': name,
            'value_label': f'{float(value):,.1f}'.removesuffix('.0') if valid else 'Not available',
            'records_label': f"{int(row['attack_rows']):,}" if row is not None and pd.notna(row.get('attack_rows')) else 'No mapped data',
            'fill_color': color,
        }
        features.append({'type': 'Feature', 'geometry': feature['geometry'], 'properties': props})
    return {'type': 'FeatureCollection', 'features': features}, maximum


def render_region_choropleth(frame: pd.DataFrame, metric: str, metric_label: str) -> None:
    boundaries, maximum = make_region_features(load_region_boundaries(), frame, metric)
    layer = pdk.Layer('GeoJsonLayer', data=boundaries, get_fill_color='properties.fill_color',
                      get_line_color=[95, 121, 150, 180], line_width_min_pixels=1,
                      pickable=True, auto_highlight=True, stroked=True, filled=True)
    deck = pdk.Deck(
        map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
        initial_view_state=pdk.ViewState(latitude=48.9, longitude=31.5, zoom=4.6, pitch=0),
        layers=[layer],
        tooltip={'text': '{name}\n' + metric_label + ': {value_label}\nReported records: {records_label}'},
    )
    st.pydeck_chart(deck, width='stretch', height=700)
    high_color = '#53ad86' if metric == 'air_defense_success_pct' else '#e0833e'
    st.markdown(
        '<div style="display:flex;align-items:center;gap:.7rem;font-size:.85rem;flex-wrap:wrap">'
        '<span>Lower</span><span style="width:180px;height:10px;border-radius:8px;'
        f'background:linear-gradient(90deg,#2b435c,{high_color})"></span>'
        f'<span>Higher (max {maximum:,.1f})</span>'
        '<span style="margin-left:1rem;color:#8291a5">■ No value for selected metric</span></div>',
        unsafe_allow_html=True,
    )


def prepare_direction_markers(frame: pd.DataFrame, metric: str) -> tuple[list[dict], float]:
    """Map broad directional reports to illustrative points, never to individual oblasts."""
    directional = frame[(frame['target_scope'] == 'directional_or_other_macro') &
                        frame['area_macro'].isin(DIRECTION_CENTERS)].copy()
    values = pd.to_numeric(directional[metric], errors='coerce').dropna()
    maximum = 100.0 if metric == 'air_defense_success_pct' else (max(float(values.max()), 0.0) if not values.empty else 0.0)
    markers = []
    for row in directional.to_dict('records'):
        value = row.get(metric)
        if value is None or pd.isna(value):
            continue
        ratio = max(0, float(value)) / maximum if maximum > 0 else 0
        if metric != 'air_defense_success_pct':
            ratio = ratio ** 0.5
        high = [83, 173, 134, 230] if metric == 'air_defense_success_pct' else [224, 131, 62, 230]
        markers.append({
            'direction': row['area_macro'].replace('-', ' ').title(),
            'position': DIRECTION_CENTERS[row['area_macro']],
            'value_label': f'{float(value):,.1f}'.removesuffix('.0'),
            'records_label': f"{int(row['attack_rows']):,}",
            'color': interpolate_rgba([43, 67, 92, 230], high, ratio),
        })
    return markers, maximum


def render_direction_map(frame: pd.DataFrame, metric: str, metric_label: str) -> None:
    markers, maximum = prepare_direction_markers(frame, metric)
    if not markers:
        st.info('No directional data is available for this metric in the selected period.')
        return
    regions = pdk.Layer('GeoJsonLayer', data=load_region_boundaries(),
                        get_fill_color=[29, 42, 59, 220], get_line_color=[95, 121, 150, 180],
                        line_width_min_pixels=1, stroked=True, filled=True)
    points = pdk.Layer('ScatterplotLayer', data=markers, get_position='position',
                       get_fill_color='color', get_radius=30000, radius_min_pixels=14,
                       radius_max_pixels=22, stroked=True, get_line_color=[238, 245, 255, 220],
                       line_width_min_pixels=2, pickable=True, auto_highlight=True)
    labels = pdk.Layer('TextLayer', data=markers, get_position='position', get_text='direction',
                       get_color=[240, 245, 255, 255], get_size=14, get_pixel_offset=[0, -30],
                       get_text_anchor='middle', get_alignment_baseline='center')
    deck = pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
                    initial_view_state=pdk.ViewState(latitude=48.9, longitude=31.5, zoom=4.6, pitch=0),
                    layers=[regions, points, labels],
                    tooltip={'text': '{direction}\n' + metric_label + ': {value_label}\nReported records: {records_label}'})
    st.pydeck_chart(deck, width='stretch', height=700)
    high_color = '#53ad86' if metric == 'air_defense_success_pct' else '#e0833e'
    st.markdown(
        '<div style="display:flex;align-items:center;gap:.7rem;font-size:.85rem">'
        '<span>Lower</span><span style="width:180px;height:10px;border-radius:8px;'
        f'background:linear-gradient(90deg,#2b435c,{high_color})"></span>'
        f'<span>Higher (max {maximum:,.1f})</span></div>', unsafe_allow_html=True,
    )
    st.caption(f'Color intensity uses the selected metric; scale maximum: {maximum:,.1f}.'
               ' Count colors use a square-root scale; percentages use a 0–100% scale.')


def pick_available_column(frame, preferred: str, fallback: str) -> str:
    """Return the preferred column when available, otherwise use a safe fallback."""
    return preferred if preferred in frame.columns else fallback


def interpolate_rgba(start_color: list[int], end_color: list[int], ratio: float) -> list[int]:
    """Blend between two RGBA colors with a clamped linear ratio."""
    ratio = max(0.0, min(1.0, float(ratio)))
    return [
        round(start_channel + (end_channel - start_channel) * ratio)
        for start_channel, end_channel in zip(start_color, end_color)
    ]


def add_map_marker_columns(
    frame,
    color_value_column: str,
    size_value_column: str,
    color_scheme: str = "red",
):
    """Add pydeck-compatible marker size and color columns."""
    map_frame = frame.copy()

    max_size_value = map_frame[size_value_column].max()
    if max_size_value and max_size_value > 0:
        size_ratio = (map_frame[size_value_column] / max_size_value).pow(0.5)
        map_frame["marker_size"] = (15_000 + size_ratio * 85_000).round(0)
    else:
        map_frame["marker_size"] = 24_000

    max_color_value = map_frame[color_value_column].max()

    def marker_color(value):
        color_ranges = {
            "red": ([255, 228, 230, 150], [127, 0, 0, 190]),
            "green": ([220, 252, 231, 150], [22, 101, 52, 190]),
        }
        start_color, end_color = color_ranges[color_scheme]

        if not max_color_value or max_color_value <= 0:
            return end_color

        ratio = value / max_color_value
        return interpolate_rgba(start_color, end_color, ratio)

    map_frame["marker_color"] = map_frame[color_value_column].apply(marker_color)
    return map_frame


def render_map_legend(metric_label: str, size_label: str, color_scheme: str) -> None:
    """Render a compact visual legend for map marker color and size."""
    if color_scheme == "green":
        gradient = (
            "linear-gradient(90deg, #dcfce7 0%, #b7e8c1 20%, #86d19a 40%, "
            "#56ba73 60%, #2f944f 80%, #166534 100%)"
        )
        accent = "#166534"
        border = "#bbf7d0"
        background = "#f8fffb"
    else:
        gradient = (
            "linear-gradient(90deg, #ffe4e6 0%, #ffc2c7 20%, #ff9494 40%, "
            "#f85b5b 60%, #cc2020 80%, #7f0000 100%)"
        )
        accent = "#991b1b"
        border = "#fecdd3"
        background = "#fff8f8"

    st.markdown(
        f"""
        <div style="
            border: 1px solid {border};
            border-radius: 8px;
            padding: 0.9rem;
            margin-top: 0.25rem;
            background: {background};
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
        ">
            <div style="font-size: 0.82rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: {accent}; margin-bottom: 0.7rem;">
                Map guide
            </div>
            <div style="font-weight: 600; color: #111827; margin-bottom: 0.38rem;">Color intensity</div>
            <div style="
                height: 12px;
                border-radius: 999px;
                background: {gradient};
                border: 1px solid rgba(17, 24, 39, 0.08);
                margin-bottom: 0.3rem;
            "></div>
            <div style="
                display: flex;
                justify-content: space-between;
                font-size: 0.84rem;
                color: #4b5563;
                margin-bottom: 0.8rem;
            ">
                <span>Lower {metric_label.lower()}</span>
                <span>Higher {metric_label.lower()}</span>
            </div>
            <div style="font-weight: 600; color: #111827; margin-bottom: 0.45rem;">Marker size</div>
            <div style="display: flex; align-items: flex-end; gap: 0.65rem; margin-bottom: 0.35rem;">
                <div style="
                    width: 12px;
                    height: 12px;
                    border-radius: 999px;
                    background: rgba(107, 114, 128, 0.5);
                    border: 1px solid rgba(75, 85, 99, 0.35);
                "></div>
                <div style="
                    width: 22px;
                    height: 22px;
                    border-radius: 999px;
                    background: rgba(107, 114, 128, 0.42);
                    border: 1px solid rgba(75, 85, 99, 0.35);
                "></div>
                <div style="
                    width: 34px;
                    height: 34px;
                    border-radius: 999px;
                    background: rgba(107, 114, 128, 0.34);
                    border: 1px solid rgba(75, 85, 99, 0.35);
                "></div>
            </div>
            <div style="font-size: 0.84rem; color: #4b5563; margin-bottom: 0.8rem;">
                Larger circles mean higher {size_label.lower()}.
            </div>
            <div style="
                font-size: 0.82rem;
                color: #6b7280;
                line-height: 1.4;
                padding-top: 0.7rem;
                border-top: 1px solid rgba(148, 163, 184, 0.22);
            ">
                Points use approximate centroids, not exact strike coordinates or boundaries.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_point_map(frame, tooltip_text: str, height: int) -> None:
    """Render a pydeck point map with hover tooltip support."""
    point_layer = pdk.Layer(
        "ScatterplotLayer",
        data=frame,
        get_position="[lon, lat]",
        get_radius="marker_size",
        get_fill_color="marker_color",
        pickable=True,
        auto_highlight=True,
    )
    view_state = pdk.ViewState(
        latitude=48.9,
        longitude=31.5,
        zoom=5.1,
        pitch=0,
    )
    deck = pdk.Deck(
        map_style=None,
        initial_view_state=view_state,
        layers=[point_layer],
        tooltip={"text": tooltip_text},
    )
    st.pydeck_chart(deck, width="stretch", height=height)
