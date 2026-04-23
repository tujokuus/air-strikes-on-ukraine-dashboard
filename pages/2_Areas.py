from __future__ import annotations

import plotly.graph_objects as go
import plotly.express as px
import pydeck as pdk
import streamlit as st

from dashboard.data import ensure_gold_database, query


st.set_page_config(page_title="Areas", layout="wide")
st.title("Areas")
st.caption("Target macro areas, directional summaries, and centroid maps.")

# Stop early if the pipeline has not built the gold database yet.
ensure_gold_database()

# Load area-level marts from the gold layer.
area_macros = query("SELECT * FROM vw_dashboard_area_macros")
directional = query("SELECT * FROM vw_dashboard_directional_macros")
region_map = query("SELECT * FROM vw_dashboard_region_map")

# Combine target scopes for the main dashboard chart so each area macro appears only once.
area_macros_chart = (
    area_macros.groupby("area_macro", as_index=False)
    .agg(
        attack_rows=("attack_rows", "sum"),
        active_days=("active_days", "max"),
        launched_total=("launched_total", "sum"),
        destroyed_total=("destroyed_total", "sum"),
    )
    .sort_values(["launched_total", "attack_rows"], ascending=[False, False])
)
area_macros_chart["launched_share_pct"] = (
    100.0
    * area_macros_chart["launched_total"]
    / area_macros_chart["launched_total"].sum()
).round(2)
area_macros_chart["strike_record_share_pct"] = (
    100.0
    * area_macros_chart["attack_rows"]
    / area_macros_chart["attack_rows"].sum()
).round(2)
area_macros_chart["air_defense_success_pct"] = (
    100.0
    * area_macros_chart["destroyed_total"]
    / area_macros_chart["launched_total"].replace({0: None})
).round(2)


def area_macro_value(area_macro: str, column: str):
    """Return one summary value for a combined area macro row."""
    values = area_macros_chart.loc[area_macros_chart["area_macro"] == area_macro, column]
    if values.empty:
        return 0
    return values.iloc[0]


def pick_available_column(frame, preferred: str, fallback: str) -> str:
    """Return the preferred column when available, otherwise use a safe fallback."""
    return preferred if preferred in frame.columns else fallback


def add_map_marker_columns(frame, color_value_column: str, size_value_column: str):
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
        if not max_color_value or max_color_value <= 0:
            return [127, 0, 0, 180]

        ratio = value / max_color_value
        if ratio >= 0.75:
            return [127, 0, 0, 190]
        if ratio >= 0.50:
            return [204, 0, 0, 180]
        if ratio >= 0.25:
            return [255, 77, 77, 170]
        return [255, 153, 153, 160]

    map_frame["marker_color"] = map_frame[color_value_column].apply(marker_color)
    return map_frame


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


st.subheader("Area Macro Summary")

# Let the user choose one or both metrics for the area macro chart.
col1, col2 = st.columns(2)

with col1:
    show_launched_total = st.toggle("Launched total", value=True)

with col2:
    show_strike_records = st.toggle("Strike records", value=False)

# Log scale is helpful because nationwide rows are much larger than most specific regions.
use_log = st.toggle("Use log scale", value=True)

if show_launched_total and show_strike_records:
    fig = go.Figure()
    fig.add_bar(
        x=area_macros_chart["area_macro"],
        y=area_macros_chart["launched_total"],
        name="Launched total",
        marker_color="#9e1e1e",
        offsetgroup="launched",
        yaxis="y",
    )
    fig.add_bar(
        x=area_macros_chart["area_macro"],
        y=area_macros_chart["attack_rows"],
        name="Strike records",
        marker_color="#2d6a4f",
        offsetgroup="records",
        yaxis="y2",
    )
    fig.update_layout(
        title="Launched total and strike records by area macro",
        xaxis_title="Area macro",
        yaxis=dict(title="Launched total", type="log" if use_log else "linear"),
        yaxis2=dict(
            title="Strike records",
            overlaying="y",
            side="right",
            type="log" if use_log else "linear",
        ),
        barmode="group",
        legend_title_text="",
    )
elif show_strike_records:
    fig = px.bar(
        area_macros_chart,
        x="area_macro",
        y="attack_rows",
        text="attack_rows",
        hover_data=["launched_total", "destroyed_total", "air_defense_success_pct", "launched_share_pct"],
        color_discrete_sequence=["#2d6a4f"],
        title="Strike records by area macro",
        labels={
            "area_macro": "Area macro",
            "attack_rows": "Strike records",
            "launched_total": "Launched total",
            "destroyed_total": "Destroyed total",
            "air_defense_success_pct": "Air defense success %",
            "launched_share_pct": "Launched share %",
        },
    )
    fig.update_layout(xaxis_title="Area macro", yaxis_title="Strike records")
    if use_log:
        fig.update_yaxes(type="log")
elif show_launched_total:
    fig = px.bar(
        area_macros_chart,
        x="area_macro",
        y="launched_total",
        text="launched_total",
        hover_data=["attack_rows", "destroyed_total", "air_defense_success_pct", "launched_share_pct"],
        color_discrete_sequence=["#9e1e1e"],
        title="Launched total by area macro",
        labels={
            "area_macro": "Area macro",
            "attack_rows": "Strike records",
            "launched_total": "Launched total",
            "destroyed_total": "Destroyed total",
            "air_defense_success_pct": "Air defense success %",
            "launched_share_pct": "Launched share %",
        },
    )
    fig.update_layout(xaxis_title="Area macro", yaxis_title="Launched total")
    if use_log:
        fig.update_yaxes(type="log")

if show_launched_total or show_strike_records:
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Select at least one metric to show the area macro chart.")

st.markdown(
    f"""
    <div style="
        color: #b91c1c;
        font-size: 1.08rem;
        font-weight: 700;
        border-left: 4px solid #b91c1c;
        padding: 0.75rem 1rem;
        margin: 1rem 0;
        background: #fff1f2;
    ">
        Map context: the maps only show rows that can be placed on approximate coordinates.
        Nationwide rows are {area_macro_value('nationwide', 'launched_share_pct')}% of launched total
        and {area_macro_value('nationwide', 'strike_record_share_pct')}% of strike records.
        Unknown target rows are {area_macro_value('unknown', 'launched_share_pct')}% of launched total
        and {area_macro_value('unknown', 'strike_record_share_pct')}% of strike records.
    </div>
    """,
    unsafe_allow_html=True,
)


st.subheader("Directional Macro Map")

map_metric = st.radio(
    "Map marker metric",
    ["Launched", "Strike records", "Air defense success %"],
    horizontal=True,
)
st.caption(
    "This controls marker color on the directional map. In air defense mode, marker size still follows launched total."
)

# Macro centroids give a coarse directional view, not exact strike locations.
directional_map = directional[directional["lat"].notna() & directional["lon"].notna()].copy()
directional_metric_column = (
    "launched_total"
    if map_metric == "Launched"
    else "attack_rows"
    if map_metric == "Strike records"
    else "air_defense_success_pct"
)
directional_metric_column = pick_available_column(directional_map, directional_metric_column, "launched_total")
directional_size_column = "launched_total" if map_metric == "Air defense success %" else directional_metric_column
directional_map = add_map_marker_columns(
    directional_map,
    color_value_column=directional_metric_column,
    size_value_column=directional_size_column,
)
render_point_map(
    directional_map,
    tooltip_text=(
        "{area_macro}\n"
        "Strike records: {attack_rows}\n"
        "Active days: {active_days}\n"
        "Launched total: {launched_total}\n"
        "Destroyed total: {destroyed_total}\n"
        "Air defense success %: {air_defense_success_pct}"
    ),
    height=720,
)

st.subheader("Specific Region Map")

specific_region_map_metric = st.radio(
    "Specific region map marker metric",
    ["Launched", "Strike records", "Air defense success %"],
    horizontal=True,
)
st.caption(
    "This controls marker color on the specific region map. In air defense mode, marker size still follows launched total."
)

# Drop rows without coordinates because Streamlit cannot place them on the map.
mapped_regions = region_map[region_map["lat"].notna()].copy()
show_foreign_regions = st.toggle("Show foreign regions", value=False)
if not show_foreign_regions and "area_kind" in mapped_regions.columns:
    mapped_regions = mapped_regions[mapped_regions["area_kind"] != "foreign_oblast"].copy()

region_launched_column = (
    "launched_total_allocated"
    if "launched_total_allocated" in mapped_regions.columns
    else "launched_total_exploded"
)
region_metric_column = (
    region_launched_column
    if specific_region_map_metric == "Launched"
    else "attack_rows"
    if specific_region_map_metric == "Strike records"
    else "air_defense_success_pct"
)
region_metric_column = pick_available_column(mapped_regions, region_metric_column, region_launched_column)
region_size_column = (
    region_launched_column
    if specific_region_map_metric == "Air defense success %"
    else region_metric_column
)
mapped_regions = add_map_marker_columns(
    mapped_regions,
    color_value_column=region_metric_column,
    size_value_column=region_size_column,
)
tooltip_lines = [
    "{area_region}",
    "Strike records: {attack_rows}",
    "Active days: {active_days}",
    f"{region_launched_column}: " + "{" + region_launched_column + "}",
    "Exploded launched total: {launched_total_exploded}",
    "Air defense success %: {air_defense_success_pct}",
    "Area kind: {area_kind}",
]
if "reporting_region" in mapped_regions.columns:
    tooltip_lines.insert(1, "Reporting region: {reporting_region}")
if "exploded_region_rows" in mapped_regions.columns:
    tooltip_lines.append("Exploded region rows: {exploded_region_rows}")
if "source_region_count" in mapped_regions.columns:
    tooltip_lines.append("Source regions combined: {source_region_count}")

render_point_map(
    mapped_regions,
    tooltip_text="\n".join(tooltip_lines),
    height=760,
)
