from __future__ import annotations

import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from dashboard.date_queries import (
    get_filtered_area_macros,
    get_filtered_directional_macros,
    get_filtered_region_map,
)
from dashboard.filters import get_selected_date_range
from dashboard.maps import (
    add_map_marker_columns,
    pick_available_column,
    render_map_legend,
    render_point_map,
)


st.title("Areas")
st.caption("Target macro areas, directional summaries, and centroid maps.")
selected_start, selected_end = get_selected_date_range()
st.caption(f"Selected range: {selected_start:%d.%m.%Y} - {selected_end:%d.%m.%Y}")

area_macros = get_filtered_area_macros(selected_start, selected_end)
directional = get_filtered_directional_macros(selected_start, selected_end)
region_map = get_filtered_region_map(selected_start, selected_end)

if area_macros.empty and directional.empty and region_map.empty:
    st.info("No area or map data was found in the selected date range.")
    st.stop()

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
area_macros_chart["air_defense_success_label"] = area_macros_chart[
    "air_defense_success_pct"
].map(lambda value: "" if value != value else f"{value:.1f}%")


def area_macro_value(area_macro: str, column: str):
    """Return one summary value for a combined area macro row."""
    values = area_macros_chart.loc[area_macros_chart["area_macro"] == area_macro, column]
    if values.empty:
        return 0
    return values.iloc[0]


st.subheader("Area Macro Summary")

# Let the user choose which metrics the area macro chart should display.
col1, col2, col3 = st.columns(3)

with col1:
    show_launched_total = st.toggle("Launched total", value=True)

with col2:
    show_strike_records = st.toggle("Strike records", value=False)

with col3:
    show_air_defense_success = st.toggle("Air defense success %", value=False)

# Log scale is helpful because nationwide rows are much larger than most specific regions.
use_log = st.toggle("Use log scale", value=True)

selected_metrics = [
    metric
    for metric, enabled in [
        ("launched_total", show_launched_total),
        ("attack_rows", show_strike_records),
        ("air_defense_success_pct", show_air_defense_success),
    ]
    if enabled
]

if selected_metrics == ["launched_total"]:
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
elif selected_metrics == ["attack_rows"]:
    fig = px.bar(
        area_macros_chart,
        x="area_macro",
        y="attack_rows",
        text="attack_rows",
        hover_data=["launched_total", "destroyed_total", "air_defense_success_pct", "launched_share_pct"],
        color_discrete_sequence=["#2563eb"],
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
elif selected_metrics == ["air_defense_success_pct"]:
    fig = px.bar(
        area_macros_chart,
        x="area_macro",
        y="air_defense_success_pct",
        text="air_defense_success_label",
        hover_data=["attack_rows", "launched_total", "destroyed_total", "launched_share_pct"],
        color_discrete_sequence=["#15803d"],
        title="Air defense success % by area macro",
        labels={
            "area_macro": "Area macro",
            "attack_rows": "Strike records",
            "launched_total": "Launched total",
            "destroyed_total": "Destroyed total",
            "air_defense_success_pct": "Air defense success %",
            "launched_share_pct": "Launched share %",
        },
    )
    fig.update_layout(xaxis_title="Area macro", yaxis_title="Air defense success %")
    fig.update_traces(textposition="outside")
else:
    fig = go.Figure()
    axis_count = 0

    if show_launched_total:
        axis_count += 1
        fig.add_bar(
            x=area_macros_chart["area_macro"],
            y=area_macros_chart["launched_total"],
            name="Launched total",
            marker_color="#9e1e1e",
            offsetgroup="launched",
            yaxis="y",
        )

    if show_strike_records:
        axis_name = "y2" if axis_count >= 1 else "y"
        fig.add_bar(
            x=area_macros_chart["area_macro"],
            y=area_macros_chart["attack_rows"],
            name="Strike records",
            marker_color="#2563eb",
            offsetgroup="records",
            yaxis=axis_name,
        )

    if show_air_defense_success:
        axis_name = "y3" if (show_launched_total and show_strike_records) else ("y2" if len(selected_metrics) > 1 else "y")
        fig.add_bar(
            x=area_macros_chart["area_macro"],
            y=area_macros_chart["air_defense_success_pct"],
            text=area_macros_chart["air_defense_success_label"],
            name="Air defense success %",
            marker_color="#15803d",
            offsetgroup="success",
            yaxis=axis_name,
            textposition="outside",
        )

    layout_kwargs = {
        "title": "Area macro comparison",
        "xaxis_title": "Area macro",
        "barmode": "group",
        "legend_title_text": "",
    }

    if show_launched_total:
        layout_kwargs["yaxis"] = dict(
            title="Launched total",
            type="log" if use_log else "linear",
        )

    if show_strike_records:
        strike_axis_key = "yaxis2" if show_launched_total else "yaxis"
        strike_axis = dict(
            title="Strike records",
            overlaying="y" if show_launched_total else None,
            side="right" if show_launched_total else None,
            type="log" if use_log else "linear",
        )
        if show_launched_total and show_air_defense_success:
            strike_axis["anchor"] = "free"
            strike_axis["position"] = 1.0
        layout_kwargs[strike_axis_key] = strike_axis

    if show_air_defense_success:
        if show_launched_total and show_strike_records:
            layout_kwargs["yaxis3"] = dict(
                title="Air defense success %",
                overlaying="y",
                side="right",
                anchor="free",
                position=0.92,
                range=[0, 100],
            )
            layout_kwargs["margin"] = dict(r=120)
        elif show_launched_total or show_strike_records:
            layout_kwargs["yaxis2"] = dict(
                title="Air defense success %",
                overlaying="y",
                side="right",
                range=[0, 100],
            )
        else:
            layout_kwargs["yaxis"] = dict(
                title="Air defense success %",
                range=[0, 100],
            )

    fig.update_layout(**layout_kwargs)

if selected_metrics:
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
directional_color_scheme = "green" if map_metric == "Air defense success %" else "red"
directional_map = add_map_marker_columns(
    directional_map,
    color_value_column=directional_metric_column,
    size_value_column=directional_size_column,
    color_scheme=directional_color_scheme,
)
map_col, legend_col = st.columns([4.4, 1.6], vertical_alignment="top")
with map_col:
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
with legend_col:
    render_map_legend(
        metric_label=map_metric,
        size_label="Launched total" if map_metric == "Air defense success %" else map_metric,
        color_scheme=directional_color_scheme,
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
region_color_scheme = "green" if specific_region_map_metric == "Air defense success %" else "red"
mapped_regions = add_map_marker_columns(
    mapped_regions,
    color_value_column=region_metric_column,
    size_value_column=region_size_column,
    color_scheme=region_color_scheme,
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

map_col, legend_col = st.columns([4.4, 1.6], vertical_alignment="top")
with map_col:
    render_point_map(
        mapped_regions,
        tooltip_text="\n".join(tooltip_lines),
        height=760,
    )
with legend_col:
    render_map_legend(
        metric_label=specific_region_map_metric,
        size_label="Launched total" if specific_region_map_metric == "Air defense success %" else specific_region_map_metric,
        color_scheme=region_color_scheme,
    )
