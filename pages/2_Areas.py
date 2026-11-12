from __future__ import annotations

import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from dashboard.date_queries import (
    get_filtered_area_macros,
    get_filtered_region_map,
)
from dashboard.filters import get_selected_date_range
from dashboard.maps import (
    render_direction_map,
    render_region_choropleth,
)


st.title("Areas")
st.caption("Target macro areas and regional activity.")
selected_start, selected_end = get_selected_date_range()
st.caption(f"Selected range: {selected_start:%d.%m.%Y} - {selected_end:%d.%m.%Y}")

area_macros = get_filtered_area_macros(selected_start, selected_end)
region_map = get_filtered_region_map(selected_start, selected_end)

if area_macros.empty and region_map.empty:
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

st.info(
    "**Location and security context:** These maps summarize historical public reports, not live tracking, "
    "precise impact locations or air-defense positions. Some locations are deliberately broad or missing. "
    "Air-defense percentages are calculated from reported destroyed and launched totals; reporting can be "
    "incomplete, and regional estimates are not a measure of operational effectiveness. Avoid sharing "
    "sensitive current military locations or unconfirmed strike details."
)

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
        Regional map context: only rows matched to Ukrainian region boundaries are shown.
        Nationwide rows are {area_macro_value('nationwide', 'launched_share_pct')}% of launched total
        and {area_macro_value('nationwide', 'strike_record_share_pct')}% of strike records.
        Unknown target rows are {area_macro_value('unknown', 'launched_share_pct')}% of launched total
        and {area_macro_value('unknown', 'strike_record_share_pct')}% of strike records.
    </div>
    """,
    unsafe_allow_html=True,
)


st.subheader("Reported activity by region")
st.caption(
    "Regions show reports that could be mapped to an oblast. City reports are grouped "
    "with their reporting oblast; nationwide and unknown locations are not shown. "
    "The boundary file does not include a separate Kyiv city polygon."
)
region_metric = st.radio(
    "Region color represents",
    ["Reported strike records", "Estimated allocated launched weapons", "Air defense success %"],
    horizontal=True,
)
region_metric_column = (
    "attack_rows" if region_metric == "Reported strike records" else
    "launched_total_allocated" if region_metric == "Estimated allocated launched weapons" else
    "air_defense_success_pct"
)
render_region_choropleth(region_map, region_metric_column, region_metric)
st.caption(
    "Reported strike records are dataset rows, not necessarily distinct strikes. "
    "Allocated weapons split multi-region reports evenly; they are estimates, not confirmed regional counts. "
    "Neutral regions have no value for the selected metric, not necessarily zero strikes."
)
st.caption("Count colors use a square-root scale to make lower values easier to distinguish. Percentages use a 0–100% scale.")
st.caption(
    "Boundaries: Ukrainian geojson data by slawomirmatuszak and contributors, "
    "[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); "
    "[source](https://github.com/slawomirmatuszak/ukrainian_geodata). "
    "Basemap: CARTO / OpenStreetMap contributors."
)

st.subheader("Reports by broad direction")
st.caption(
    "Only source rows described by a broad direction are included. The markers are illustrative "
    "labels for directions, not strike, launch or air-defense locations. Oblast-colored boundaries "
    "are not inferred from these reports. Nationwide, front-line and mixed-direction "
    "categories that cannot be assigned to one displayed direction are excluded."
)
direction_metric = st.radio(
    "Directional marker color represents",
    ["Reported strike records", "Reported launched weapons", "Air defense success %"],
    horizontal=True,
)
direction_metric_column = (
    "attack_rows" if direction_metric == "Reported strike records" else
    "launched_total" if direction_metric == "Reported launched weapons" else
    "air_defense_success_pct"
)
render_direction_map(area_macros, direction_metric_column, direction_metric)
